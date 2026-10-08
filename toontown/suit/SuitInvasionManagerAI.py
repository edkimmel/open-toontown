from direct.directnotify import DirectNotifyGlobal
from toontown.battle import SuitBattleGlobals

class SuitInvasionManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('SuitInvasionManagerAI')

    # The original game's random invasion scheduler (waitForNextInvasion /
    # tryInvasionAndWaitForNext) is deliberately not ported: invasions only
    # start through startInvasion (e.g. the ~invasion magic word).
    def __init__(self, air):
        self.air = air
        self.invading = 0
        self.cogType = None
        self.isSkeleton = 0
        self.totalNumCogs = 0
        self.numCogsRemaining = 0

    def getInvading(self):
        return self.invading

    def getCogType(self):
        return self.cogType, self.isSkeleton

    def getNumCogsRemaining(self):
        return self.numCogsRemaining

    def getTotalNumCogs(self):
        return self.totalNumCogs

    def startInvasion(self, cogType, totalNumCogs, skeleton=0):
        if self.invading:
            self.notify.warning('startInvasion: already invading cogType: %s numCogsRemaining: %s' % (self.cogType, self.numCogsRemaining))
            return 0
        if not SuitBattleGlobals.SuitAttributes.get(cogType):
            self.notify.warning('startInvasion: unknown cogType: %s' % cogType)
            return 0
        self.notify.info('startInvasion: cogType: %s totalNumCogs: %s skeleton: %s' % (cogType, totalNumCogs, skeleton))
        self.invading = 1
        self.cogType = cogType
        self.isSkeleton = skeleton
        self.totalNumCogs = totalNumCogs
        self.numCogsRemaining = totalNumCogs
        self.air.newsManager.invasionBegin(self.cogType, self.totalNumCogs, self.isSkeleton)
        self.__flySuits()
        return 1

    def getInvadingCog(self):
        if self.invading:
            self.numCogsRemaining -= 1
            cogType, isSkeleton = self.cogType, self.isSkeleton
            if self.numCogsRemaining <= 0:
                self.stopInvasion()
            return cogType, isSkeleton
        return None, None

    def stopInvasion(self):
        self.notify.info('stopInvasion: invasion is over now')
        self.air.newsManager.invasionEnd(self.cogType, 0, self.isSkeleton)
        self.invading = 0
        self.cogType = None
        self.isSkeleton = 0
        self.totalNumCogs = 0
        self.numCogsRemaining = 0
        self.__flySuits()

    def __flySuits(self):
        for suitPlanner in list(self.air.suitPlanners.values()):
            suitPlanner.flySuits()
