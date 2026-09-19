from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

class DistributedFishingPondAI(DistributedObjectAI):
    """The hub every fishing spot and target in a zone hangs off.

    The pond itself owns no fishing state: it keeps the registries the
    spots and targets add themselves to, and ratifies the one message the
    client sends it, `hitTarget`.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingPondAI')

    # The client polls for a hit every DistributedFishingPond.pollInterval
    # (0.5 seconds, DistributedFishingPond.py:12,60-75) and reports at most
    # one hit per cast, so no stock client can send two any closer.
    MinimumCatchInterval = 0.5

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        # The area is the canonical zone the target table and the catch
        # table are both keyed on (FishingTargetGlobals.py:145-154,
        # FishGlobals.py:715-760), never the zoneId the pond is generated
        # into: at the estate those are different numbers.
        self.area = None
        # spot doId -> DistributedFishingSpotAI
        self.spots = {}
        # target doId -> DistributedFishingTargetAI
        self.targets = {}
        # avId -> the time of their last ratified catch
        self.lastCatchTime = {}
        # One ephemeral manager is attached by EstateWorld after this pond is
        # generated.  The pond remains usable without it in non-estate zones.
        self.bingoMgr = None

    def delete(self):
        # The pond arms no tasks of its own; its spots and targets cancel
        # theirs in their own delete().
        self.spots = {}
        self.targets = {}
        self.lastCatchTime = {}
        self.bingoMgr = None
        DistributedObjectAI.delete(self)

    def setArea(self, area):
        self.area = area

    def getArea(self):
        return self.area

    def addSpot(self, spot):
        self.spots[spot.doId] = spot

    def removeSpot(self, spot):
        # tolerant of an unregister that lost the race with a zone teardown
        self.spots.pop(spot.doId, None)

    def getSpots(self):
        return list(self.spots.values())

    def getSpot(self, avId):
        """The spot avId occupies on this pond, or None."""
        if not avId:
            return None
        for spot in self.spots.values():
            if spot.getAvId() == avId:
                return spot

        return None

    def setBingoManager(self, manager):
        self.bingoMgr = manager

    def getBingoManager(self):
        return self.bingoMgr

    def addTarget(self, target):
        self.targets[target.doId] = target

    def removeTarget(self, target):
        self.targets.pop(target.doId, None)

    def hasTarget(self, targetDoId):
        return targetDoId in self.targets

    def hitTarget(self, targetDoId):
        # The client picks the catch moment and names the target
        # (DistributedFishingPond.checkTargets:60-80), so everything it
        # says is checked here before the spot resolves anything.
        avId = self.air.getAvatarIdFromSender()
        spot = self.getSpot(avId)
        if spot is None:
            self.refuseHit(avId, 'occupies no spot on pond %s' % self.doId)
            return
        if targetDoId not in self.targets:
            self.refuseHit(avId, 'named target %s, which is not on pond %s' % (targetDoId, self.doId))
            return
        if not spot.hasCastInFlight():
            self.refuseHit(avId, 'has no cast in flight on spot %s' % spot.doId)
            return
        now = globalClock.getRealTime()
        lastCatch = self.lastCatchTime.get(avId)
        if lastCatch is not None and now - lastCatch < self.MinimumCatchInterval:
            self.refuseHit(avId, 'caught again after only %.2f seconds' % (now - lastCatch))
            return
        self.lastCatchTime[avId] = now
        spot.resolveCatch(avId, targetDoId)

    def refuseHit(self, avId, reason):
        self.air.writeServerEvent('suspicious', avId, 'DistributedFishingPondAI.hitTarget %s' % reason)
        self.notify.warning('hitTarget refused: avId %s %s' % (avId, reason))
