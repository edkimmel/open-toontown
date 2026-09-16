from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import CannonGlobals


class DistributedTargetAI(DistributedObjectAI):
    """The estate pinball target the cannon shoots at (dclass
    DistributedTarget, etc/toon.dc:1013-1022).

    Unlike the cannon this is a shared prop: every toon in the zone sees the
    same target and the same high score, and there is no occupancy gate.

    `setPosition` is the only required field (:1014); the client just
    repositions its geometry with it (DistributedTarget.py:165-166).  The
    target is invisible until the AI sends `setState(enabled, score, time)`
    -- the client only unstashes its geometry when `enabled` flips to 1
    (DistributedTarget.py:95-104) -- so whoever generates a target sends
    `d_setState(1, 0, 0)` afterwards.

    `setReward` (:1016) only plays a sound client-side
    (DistributedTarget.py:110-111) and the reference has no grant code at
    all, so a hit broadcasts CannonGlobals.TARGET_HIT_REWARD and grants no
    jellybeans: an estate prop a toon can hit indefinitely is not a
    currency source.

    `setBonus` (:1018) is accepted and dropped.  Its only sender is
    `handleHitCloud` (DistributedTarget.py:137-139), reachable only through
    the disabled branch of DistributedCannon.__hitCloudPlatform
    (DistributedCannon.py:1205-1216), so there is no observable behaviour to
    port.

    Scoring is authoritative here rather than on the cannon, which only
    relays a shooter's running total (DistributedCannon.py:1480-1483).  The
    client promotes its own high score from `score * multiplier`
    (DistributedTarget.py:183-199) and trusts the `avId` in the message; the
    AI redoes the arithmetic and refuses a score claimed for somebody else,
    the way DistributedCannonAI.requestEnter refuses a second occupant
    (DistributedCannonAI.py:44).  `setCurPinballScore` is `clsend airecv`
    with no `broadcast` (:1019), so the AI cannot relay it to the other
    clients -- only the high-score pair (:1020-1021) reaches them.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTargetAI')

    def __init__(self, air, x, y, z, pinballHiScore=0, pinballHiScorer=''):
        DistributedObjectAI.__init__(self, air)
        self.posHpr = [x, y, z]
        self.pinballHiScore = pinballHiScore
        self.pinballHiScorer = pinballHiScorer
        self.hits = 0

    def getPosition(self):
        return self.posHpr

    def getPinballHiScore(self):
        return self.pinballHiScore

    def getPinballHiScorer(self):
        return self.pinballHiScorer

    def d_setState(self, enabled, score, time):
        self.sendUpdate('setState', [enabled, score, time])

    def d_setReward(self, reward):
        self.sendUpdate('setReward', [reward])

    def setResult(self, avId):
        # DistributedTarget.py:116-120 sends the shooter's own doId on a hit,
        # :133-135 sends 0 on a miss.
        senderId = self.air.getAvatarIdFromSender()
        if avId == 0:
            return
        if avId != senderId:
            self.air.writeServerEvent('suspicious', senderId,
                                      'DistributedTargetAI.setResult claimed for another avatar')
            return
        self.hits += 1
        self.d_setReward(CannonGlobals.TARGET_HIT_REWARD)

    def setBonus(self, bonus):
        self.notify.debug('setBonus %s' % bonus)

    def setCurPinballScore(self, avId, score, multiplier):
        senderId = self.air.getAvatarIdFromSender()
        if avId != senderId:
            self.air.writeServerEvent('suspicious', senderId,
                                      'DistributedTargetAI.setCurPinballScore claimed for another avatar')
            return
        curScore = score * multiplier
        if curScore <= self.pinballHiScore:
            return
        self.pinballHiScore = curScore
        toon = self.air.doId2do.get(avId)
        if toon is not None:
            self.pinballHiScorer = toon.getName()
        self.sendUpdate('setPinballHiScore', [self.pinballHiScore])
        self.sendUpdate('setPinballHiScorer', [self.pinballHiScorer])
