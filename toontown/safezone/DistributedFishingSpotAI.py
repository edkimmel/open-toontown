from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.task import Task
from toontown.fishing import FishGlobals

class DistributedFishingSpotAI(DistributedObjectAI):
    """One seat at a fishing pond: a single-occupant session that charges
    for a cast and re-broadcasts it to the rest of the zone.

    The client drops any setMovie that arrives while it has not resolved
    the occupant yet (DistributedFishingSpot.setMovie:253-255), so the
    ordering here is not cosmetic: setOccupied(avId) goes out before the
    EnterMovie, and on the way out the ExitMovie goes out before
    setOccupied(0).

    The catch itself is proposed by the client to the pond, which ratifies
    it and calls resolveCatch (DistributedFishingPondAI.hitTarget).
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingSpotAI')

    def __init__(self, air, pondDoId=0, x=0, y=0, z=0, h=0, p=0, r=0):
        DistributedObjectAI.__init__(self, air)
        self.pondDoId = pondDoId
        self.posHpr = (x, y, z, h, p, r)
        self.pond = None
        self.avId = 0
        self.castInFlight = False
        # swappable so a test can pin the outcome roll; None means
        # FishManagerAI.getCatch falls back to the real random module
        self.rNumGen = None

    def generate(self):
        DistributedObjectAI.generate(self)
        self.pond = self.air.doId2do.get(self.pondDoId)
        if self.pond is None:
            self.notify.warning('spot %s has no pond %s' % (self.doId, self.pondDoId))
        else:
            self.pond.addSpot(self)

    def delete(self):
        self.__clearCastTimeout()
        self.ignoreAll()
        if self.pond is not None:
            self.pond.removeSpot(self)
            self.pond = None
        self.avId = 0
        DistributedObjectAI.delete(self)

    def setPondDoId(self, pondDoId):
        self.pondDoId = pondDoId

    def getPondDoId(self):
        return self.pondDoId

    def setPosHpr(self, x, y, z, h, p, r):
        self.posHpr = (x, y, z, h, p, r)

    def getPosHpr(self):
        return self.posHpr

    def getAvId(self):
        """The occupant, or 0. Read by DistributedFishingPondAI.getSpot."""
        return self.avId

    def hasCastInFlight(self):
        """True between doCast and the catch or timeout that ends it."""
        return self.castInFlight

    def requestEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if self.avId:
            self.sendUpdateToAvatarId(avId, 'rejectEnter', [])
            self.air.writeServerEvent('suspicious', avId,
                                      'DistributedFishingSpotAI.requestEnter spot already occupied')
            self.notify.warning('requestEnter() - spot %s already occupied' % self.doId)
            return
        self.avId = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleUnexpectedExit, extraArgs=[avId])
        # setOccupied first, always: the movie is silently dropped until the
        # client has an avatar to play it on (DistributedFishingSpot.py:253-255)
        self.d_setOccupied(avId)
        self.d_setMovie(FishGlobals.EnterMovie)

    def requestExit(self):
        avId = self.air.getAvatarIdFromSender()
        if not self.__isOccupant(avId, 'requestExit'):
            return
        self.__release()

    def doCast(self, power, heading):
        avId = self.air.getAvatarIdFromSender()
        if not self.__isOccupant(avId, 'doCast'):
            return
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('doCast() - unknown avatar %s' % avId)
            return
        if len(av.fishTank) >= av.getMaxFishTank():
            # the same refusal addFishToTank makes (DistributedToonAI.py:1537-1541),
            # made before the money is taken instead of after the catch
            self.d_setMovie(FishGlobals.PullInMovie, FishGlobals.OverTankLimit)
            return
        castCost = FishGlobals.getCastCost(av.getFishingRod())
        if not av.takeMoney(castCost):
            self.notify.warning('doCast() - avatar %s cannot pay %s' % (avId, castCost))
            return
        self.castInFlight = True
        self.__armCastTimeout()
        # for the onlookers only: the caster's own client skips this branch
        # (DistributedFishingSpot.py:261-263)
        self.d_setMovie(FishGlobals.CastMovie, power=power, h=heading)

    def resolveCatch(self, avId, targetDoId):
        """The one call the pond makes once it has ratified a hitTarget
        (DistributedFishingPondAI.hitTarget). The cast ends here whatever
        the outcome turns out to be."""
        if avId != self.avId:
            self.notify.warning('resolveCatch() - avatar %s does not occupy spot %s' % (avId, self.doId))
            return
        self.__clearCastTimeout()
        self.castInFlight = False
        self.sendCatch(avId, targetDoId)

    def sendCatch(self, avId, targetDoId):
        """Answer the catch on this spot with
        setMovie(PullInMovie, code, itemDesc1, itemDesc2, itemDesc3, 0, 0),
        which the client decodes in enterReward
        (DistributedFishingSpot.py:958-985).

        The outcome comes from air.fishManager.getCatch(av, area), which
        pays out any jellybeans itself, so nothing here touches money."""
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('sendCatch() - unknown avatar %s' % avId)
            return
        if self.pond is None:
            self.notify.warning('sendCatch() - spot %s has no pond' % self.doId)
            return
        code, itemDesc1, itemDesc2, itemDesc3 = self.air.fishManager.getCatch(
            av, self.pond.getArea(), self.rNumGen)
        self.d_setMovie(FishGlobals.PullInMovie, code, itemDesc1, itemDesc2, itemDesc3)

    def sellFish(self):
        """Sell the tank at the pond rather than at a fisherman.

        A stock client only offers this when the pond has a bingo manager
        (DistributedFishingSpot.__allowSellFish:1048-1054) and nothing
        generates a DistributedPondBingoManagerAI, so this is the protocol
        half of a path no client reaches today."""
        avId = self.air.getAvatarIdFromSender()
        if not self.__isOccupant(avId, 'sellFish'):
            return
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('sellFish() - unknown avatar %s' % avId)
            return
        trophyResult = self.air.fishManager.creditFishTank(av)
        self.sendUpdateToAvatarId(avId, 'sellFishComplete',
                                  [trophyResult and 1 or 0, len(av.fishCollection)])

    def d_setOccupied(self, avId):
        self.sendUpdate('setOccupied', [avId])

    def d_setMovie(self, mode, code=0, itemDesc1=0, itemDesc2=0, itemDesc3=0,
                   power=0, h=0):
        self.sendUpdate('setMovie', [mode, code, itemDesc1, itemDesc2,
                                     itemDesc3, power, h])

    def __isOccupant(self, avId, methodName):
        if avId != 0 and avId == self.avId:
            return True
        self.air.writeServerEvent('suspicious', avId,
                                  'DistributedFishingSpotAI.%s from a non-occupant' % methodName)
        self.notify.warning('%s() - avatar %s does not occupy spot %s' % (methodName, avId, self.doId))
        return False

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar:' + str(avId) + ' has exited unexpectedly')
        if avId == self.avId:
            self.__release()

    def __release(self):
        self.__clearCastTimeout()
        self.castInFlight = False
        avId = self.avId
        if avId:
            self.ignore(self.air.getAvatarExitEvent(avId))
        self.d_setMovie(FishGlobals.ExitMovie)
        self.avId = 0
        self.d_setOccupied(0)

    def __castTimeoutName(self):
        return self.uniqueName('castTimeout')

    def __armCastTimeout(self):
        # Only the client counts a cast down (DistributedFishingSpot.py:899),
        # so without this an occupant who stops sending anything keeps the
        # spot and its cast forever.
        self.__clearCastTimeout()
        taskMgr.doMethodLater(FishGlobals.CastTimeout, self.__castTimedOut,
                              self.__castTimeoutName())

    def __clearCastTimeout(self):
        taskMgr.remove(self.__castTimeoutName())

    def __castTimedOut(self, task):
        self.notify.warning('cast from avatar %s never landed' % self.avId)
        self.castInFlight = False
        self.d_setMovie(FishGlobals.NoMovie)
        return Task.done
