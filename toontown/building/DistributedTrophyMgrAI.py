from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class DistributedTrophyMgrAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTrophyMgrAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.leaderInfo = ([], [], [])
        # `DistributedBuildingAI.updateSavedBy` gives this manager one floor
        # count for every current building saver and removes that same count
        # when the building is retaken.  This is therefore an in-memory view
        # of currently saved buildings, not a persistent lifetime statistic.
        self.trophyScores = {}
        self.trophyNames = {}

    def requestTrophyScore(self):
        avId = self.air.getAvatarIdFromSender()
        avatar = self.air.doId2do.get(avId)
        if avatar is None:
            self.notify.warning('requestTrophyScore() - unknown avatar %s' % avId)
            return
        avatar.d_setTrophyScore(self.trophyScores.get(avId, 0))

    def getLeaderInfo(self):
        return self.leaderInfo

    def addTrophy(self, avId, name, numFloors):
        self.trophyNames[avId] = name
        self.trophyScores[avId] = self.trophyScores.get(avId, 0) + numFloors
        self.__sendTrophyScore(avId)
        self.__refreshLeaderInfo()

    def removeTrophy(self, avId, numFloors):
        score = self.trophyScores.get(avId, 0) - numFloors
        if score > 0:
            self.trophyScores[avId] = score
        else:
            self.trophyScores.pop(avId, None)
            self.trophyNames.pop(avId, None)
        self.__sendTrophyScore(avId)
        self.__refreshLeaderInfo()

    def __sendTrophyScore(self, avId):
        avatar = self.air.doId2do.get(avId)
        if avatar is not None:
            avatar.d_setTrophyScore(self.trophyScores.get(avId, 0))

    def __refreshLeaderInfo(self):
        # HQ renders ten rows (`DistributedHQInterior.numLeaders`).  Python's
        # stable sort preserves arrival order for tied floor totals without
        # adding an unproven tie-break rule.
        leaders = sorted(self.trophyScores, key=lambda avId: self.trophyScores[avId],
                         reverse=True)[:10]
        self.leaderInfo = ([avId for avId in leaders],
                           [self.trophyNames[avId] for avId in leaders],
                           [self.trophyScores[avId] for avId in leaders])
        # DistributedHQInteriorAI first marks itself dirty, then sends the
        # pickled `getLeaderInfo()` snapshot on the flush event.
        messenger.send('leaderboardChanged')
        messenger.send('leaderboardFlush')
