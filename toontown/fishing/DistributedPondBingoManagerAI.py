"""Server authority for one live pond's Fishing Bingo round.

The client owns presentation and derives the same card from ``tileSeed``;
this object owns every mutable fact: the generated card, marks, catches,
phase and payout.  It deliberately receives a catch only from the fishing
spot after the pond has ratified a target hit and FishManagerAI has rolled it.
"""

import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task

from toontown.fishing import BingoGlobals, FishGlobals
from toontown.fishing.BlockoutBingo import BlockoutBingo
from toontown.fishing.DiagonalBingo import DiagonalBingo
from toontown.fishing.FourCornerBingo import FourCornerBingo
from toontown.fishing.NormalBingo import NormalBingo
from toontown.fishing.ThreewayBingo import ThreewayBingo


class DistributedPondBingoManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPondBingoManagerAI')

    CardClasses = {
        BingoGlobals.NORMAL_CARD: NormalBingo,
        BingoGlobals.FOURCORNER_CARD: FourCornerBingo,
        BingoGlobals.DIAGONAL_CARD: DiagonalBingo,
        BingoGlobals.THREEWAY_CARD: ThreewayBingo,
        BingoGlobals.BLOCKOUT_CARD: BlockoutBingo,
    }
    Playing = 'Playing'
    Reward = 'Reward'
    GameOver = 'GameOver'
    WaitCountdown = 'WaitCountdown'
    RewardDelay = 5.0
    WaitDelay = 15.0

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.pondDoId = 0
        self.pond = None
        self.card = None
        self.cardId = 0
        self.typeId = BingoGlobals.NORMAL_CARD
        self.tileSeed = 0
        self.state = 'Off'
        # The timestamp is part of the distributed state, not a per-client
        # observation.  A late entrant must receive the time this phase
        # began so the client computes its remaining duration correctly.
        self.stateTimestamp = 0
        self.jackpot = 0
        self.winnerReady = False
        self.rewarded = False
        self.rewardedAvIds = set()
        # avId -> exact authoritative (genus, species), including BingoBoot.
        self.pendingCatches = {}
        self._deleted = False

    # setPondDoId is the sole required field in toon.dc for this DO.
    def setPondDoId(self, pondDoId):
        self.pondDoId = pondDoId
        self.pond = self.air.doId2do.get(pondDoId)

    def getPondDoId(self):
        return self.pondDoId

    def generate(self):
        DistributedObjectAI.generate(self)
        # A generated manager is always attached to its already-generated
        # pond.  Do not create a second manager if a stale lifecycle callback
        # tries to generate this object after its pond has gone away.
        self.pond = self.air.doId2do.get(self.pondDoId)
        if self.pond is None:
            self.notify.warning('bingo manager %s has no pond %s' %
                                (self.doId, self.pondDoId))
            return
        self.pond.setBingoManager(self)

    def delete(self):
        self._shutdown()
        if self.pond is not None and self.pond.getBingoManager() is self:
            self.pond.setBingoManager(None)
        self.pond = None
        DistributedObjectAI.delete(self)

    def requestDelete(self):
        # StateServer deletion is asynchronous.  Stop mutable gameplay before
        # its EXIT_AI reaches us so an expiry task cannot write into a pond
        # already being torn down.
        self._shutdown()
        DistributedObjectAI.requestDelete(self)

    # --- lifecycle ----------------------------------------------------

    def beginGame(self, typeId=None, tileSeed=None):
        """Start a server-selected card immediately.

        Optional arguments are deliberately ordinary Python arguments, not
        distributed fields: deterministic tests use them while production
        chooses both values on the AI.
        """
        if self._deleted or self.pond is None:
            return
        self._cancelTasks()
        if typeId is None:
            typeId = random.randrange(BingoGlobals.BLOCKOUT_CARD + 1)
        if typeId not in self.CardClasses:
            raise ValueError('unknown Bingo card type %s' % (typeId,))
        if tileSeed is None:
            tileSeed = random.randrange(0, 65536)

        self.cardId = (self.cardId + 1) & 65535
        self.typeId = typeId
        self.tileSeed = tileSeed
        self.card = self.CardClasses[typeId]()
        self.card.generateCard(tileSeed, self.pond.getArea())
        self.jackpot = BingoGlobals.getJackpot(typeId)
        self.pendingCatches = {}
        self.winnerReady = False
        self.rewarded = False
        # Payout eligibility is per card, not per manager lifetime.  The
        # same toon must be eligible again after the countdown starts a new
        # round.
        self.rewardedAvIds = set()
        self._sendCardState()
        self._sendJackpot()
        self._setState(self.Playing)
        self._arm(self._gameTaskName(), BingoGlobals.getGameTime(typeId),
                  self._gameExpired)

    def _gameExpired(self, task):
        if not self._deleted and self.state == self.Playing:
            self._finish(self.GameOver)
        return Task.done

    def _finish(self, terminalState):
        """Enter Reward/GameOver once, then schedule the next card."""
        if self._deleted or self.state != self.Playing:
            return
        self._cancel(self._gameTaskName())
        self.pendingCatches = {}
        self._setState(terminalState)
        self._arm(self._nextTaskName(), self.RewardDelay, self._waitFinished)

    def _waitFinished(self, task):
        if self._deleted:
            return Task.done
        self._setState(self.WaitCountdown)
        self._arm(self._nextTaskName(), self.WaitDelay, self._startNextGame)
        return Task.done

    def _startNextGame(self, task):
        self.beginGame()
        return Task.done

    # --- catch and card authority ------------------------------------

    def ratifyCatch(self, avId, code, genus, species):
        """Record exactly one canonical catch from this pond's spot.

        The client never calls this method.  Fish codes retain their exact
        genus/species; an old boot becomes the one explicit wildcard tuple.
        Non-card outcomes deliberately clear any older pending catch.
        """
        if self._deleted or self.state != self.Playing:
            return
        if self._spotFor(avId) is None:
            return
        self.pendingCatches.pop(avId, None)
        if code in (FishGlobals.FishItem, FishGlobals.FishItemNewEntry,
                    FishGlobals.FishItemNewRecord):
            self.pendingCatches[avId] = (genus, species)
        elif code == FishGlobals.BootItem:
            self.pendingCatches[avId] = FishGlobals.BingoBoot

    def cardUpdate(self, cardId, cellId, genus, species):
        avId = self.air.getAvatarIdFromSender()
        if (self._deleted or self.state != self.Playing or
                cardId != self.cardId or self._spotFor(avId) is None or
                not self._validCell(cellId)):
            self._refuse(avId, 'invalid card update')
            return
        # A ratified catch can mark only its matching unmarked cell.  An
        # accidental wrong click must not destroy a legitimate catch: the
        # stock UI leaves it selectable until a valid mark succeeds.
        catch = self.pendingCatches.get(avId)
        if catch is None or catch != (genus, species):
            self._refuse(avId, 'unratified catch')
            return
        if self.card.gameState & (1 << cellId):
            self._refuse(avId, 'already marked cell')
            return
        # The wire tuple must match the server's catch exactly, but Bingo
        # card cells intentionally match fish by genus.  That is the client
        # card contract too; only the canonical old-boot tuple is wildcard.
        if (catch != FishGlobals.BingoBoot and
                self.card.cellList[cellId][0] != catch[0]):
            self._refuse(avId, 'catch does not match cell')
            return

        self.pendingCatches.pop(avId, None)
        self.card.gameState |= 1 << cellId
        if self._hasBingo():
            self.winnerReady = True
        self._sendGameState(cellId)

    def handleBingoCall(self, cardId):
        avId = self.air.getAvatarIdFromSender()
        if (self._deleted or self.state != self.Playing or cardId != self.cardId
                or self._spotFor(avId) is None or self.rewarded
                or not self._hasBingo()):
            self._refuse(avId, 'invalid bingo call')
            return
        # Set the latch before money writes or state distribution.  A reentrant
        # or duplicate client datagram cannot pay this card twice.
        self.rewarded = True
        for spot in self.pond.getSpots():
            occupantId = spot.getAvId()
            # The normal spot protocol grants one toon one spot, but retain
            # the exact once-per-current-Toon reward invariant if teardown or
            # a malformed registry temporarily presents a duplicate entry.
            if not occupantId or occupantId in self.rewardedAvIds:
                continue
            self.rewardedAvIds.add(occupantId)
            toon = self.air.doId2do.get(occupantId)
            if toon is not None:
                toon.addMoney(self.jackpot)
        self._finish(self.Reward)

    def syncPlayer(self, avId):
        """Give a newly occupied spot the current shared authoritative state."""
        if self._deleted or self.card is None or self._spotFor(avId) is None:
            return
        self.sendUpdateToAvatarId(avId, 'setCardState',
                                  [self.cardId, self.typeId, self.tileSeed,
                                   self.card.gameState])
        self.sendUpdateToAvatarId(avId, 'setJackpot', [self.jackpot])
        self.sendUpdateToAvatarId(avId, 'setState',
                                  [self.state, self.stateTimestamp])

    def dropPlayer(self, avId):
        self.pendingCatches.pop(avId, None)

    # --- distribution / small helpers --------------------------------

    def _sendCardState(self):
        self._sendToOccupants('setCardState', [self.cardId, self.typeId,
                                               self.tileSeed, self.card.gameState])

    def _sendGameState(self, cellId):
        self._sendToOccupants('updateGameState', [self.card.gameState, cellId])

    def _sendJackpot(self):
        self._sendToOccupants('setJackpot', [self.jackpot])

    def _setState(self, state):
        self.state = state
        self.stateTimestamp = self._networkTime()
        self._sendToOccupants('setState', [state, self.stateTimestamp])

    def _sendToOccupants(self, fieldName, args):
        """Deliver a dynamic field to each live pond occupant exactly once.

        The historical Bingo DC fields are intentionally not ``broadcast``.
        Sending them to the StateServer therefore does not forward a dynamic
        change to interested clients.  Targeting the currently occupied
        puppet channels keeps the existing no-DC contract and mirrors the
        established late-entry sync path.
        """
        if self.pond is None:
            return
        sent = set()
        for spot in self.pond.getSpots():
            avId = spot.getAvId()
            if (not avId or avId in sent or
                    self.air.doId2do.get(avId) is None):
                continue
            sent.add(avId)
            self.sendUpdateToAvatarId(avId, fieldName, args)

    def _networkTime(self):
        return globalClockDelta.getRealNetworkTime()

    def _spotFor(self, avId):
        if self.pond is None:
            return None
        return self.pond.getSpot(avId)

    def _validCell(self, cellId):
        return isinstance(cellId, int) and not isinstance(cellId, bool) and \
            0 <= cellId < BingoGlobals.CARD_SIZE and cellId != BingoGlobals.CARD_SIZE // 2

    def _hasBingo(self):
        """Evaluate the current shared bitset without client/UI helpers.

        The client classes are presentation-side implementations and some
        retain Python-2 division in ``checkForBingo``.  The server uses the
        explicit five card contracts here so a payout is never delegated to
        client state or a UI callback.
        """
        state = self.card.gameState

        def allMarked(cells):
            return all(state & (1 << cellId) for cellId in cells)

        rows = [range(row * BingoGlobals.CARD_COLS,
                      (row + 1) * BingoGlobals.CARD_COLS)
                for row in range(BingoGlobals.CARD_ROWS)]
        cols = [range(col, BingoGlobals.CARD_SIZE, BingoGlobals.CARD_COLS)
                for col in range(BingoGlobals.CARD_COLS)]
        forward = range(0, BingoGlobals.CARD_SIZE, BingoGlobals.CARD_COLS + 1)
        backward = range(BingoGlobals.CARD_COLS - 1,
                         BingoGlobals.CARD_SIZE - 1,
                         BingoGlobals.CARD_COLS - 1)
        if self.typeId == BingoGlobals.NORMAL_CARD:
            return any(allMarked(line) for line in rows + cols + [forward, backward])
        if self.typeId == BingoGlobals.FOURCORNER_CARD:
            return allMarked((0, BingoGlobals.CARD_COLS - 1,
                              BingoGlobals.CARD_SIZE - BingoGlobals.CARD_COLS,
                              BingoGlobals.CARD_SIZE - 1))
        if self.typeId == BingoGlobals.DIAGONAL_CARD:
            return allMarked(forward) and allMarked(backward)
        if self.typeId == BingoGlobals.THREEWAY_CARD:
            return (allMarked(rows[BingoGlobals.CARD_ROWS // 2]) and
                    allMarked(forward) and allMarked(backward))
        if self.typeId == BingoGlobals.BLOCKOUT_CARD:
            return allMarked(range(BingoGlobals.CARD_SIZE))
        return False

    def _refuse(self, avId, reason):
        self.air.writeServerEvent('suspicious', avId,
                                  'DistributedPondBingoManagerAI %s' % reason)

    def _gameTaskName(self):
        return self.uniqueName('bingoGame')

    def _nextTaskName(self):
        return self.uniqueName('bingoNext')

    def _cancel(self, name):
        taskMgr.remove(name)

    def _cancelTasks(self):
        self._cancel(self._gameTaskName())
        self._cancel(self._nextTaskName())

    def _shutdown(self):
        self._deleted = True
        self._cancelTasks()
        self.pendingCatches = {}
        self.rewardedAvIds = set()

    def _arm(self, name, delay, callback):
        self._cancel(name)
        taskMgr.doMethodLater(delay, callback, name)
