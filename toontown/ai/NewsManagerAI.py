from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.toonbase import ToontownGlobals

class NewsManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('NewsManagerAI')

    def getWeeklyCalendarHolidays(self):
        return []

    def getYearlyCalendarHolidays(self):
        return []

    def getOncelyCalendarHolidays(self):
        return []

    def getRelativelyCalendarHolidays(self):
        return []

    def getMultipleStartHolidays(self):
        return []

    def generate(self):
        DistributedObjectAI.generate(self)
        self.accept('avatarEntered', self.__handleAvatarEntered)

    def __handleAvatarEntered(self, avatar):
        self.sendUpdateToAvatarId(avatar.getDoId(), 'setHolidayIdList', [self.getHolidayIdList()])
        if self.air.suitInvasionManager.getInvading():
            cogType, skeleton = self.air.suitInvasionManager.getCogType()
            numRemaining = self.air.suitInvasionManager.getNumCogsRemaining()
            self.sendAvatarInvasionStatus(avatar.getDoId(), cogType, numRemaining, skeleton)

    def getHolidayIdList(self):
        return list(self.air.holidayManager.currentHolidays)

    def sendHolidayIdList(self):
        self.sendUpdate('setHolidayIdList', [self.getHolidayIdList()])

    def invasionBegin(self, cogType, numRemaining, skeleton):
        self.sendUpdate('setInvasionStatus', [ToontownGlobals.SuitInvasionBegin, cogType, numRemaining, skeleton])

    def invasionEnd(self, cogType, numRemaining, skeleton):
        self.sendUpdate('setInvasionStatus', [ToontownGlobals.SuitInvasionEnd, cogType, numRemaining, skeleton])

    def invasionUpdate(self, cogType, numRemaining, skeleton):
        self.sendUpdate('setInvasionStatus', [ToontownGlobals.SuitInvasionUpdate, cogType, numRemaining, skeleton])

    def sendAvatarInvasionStatus(self, avId, cogType, numRemaining, skeleton):
        self.sendUpdateToAvatarId(avId, 'setInvasionStatus', [ToontownGlobals.SuitInvasionBulletin, cogType, numRemaining, skeleton])
