import time
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.catalog import CatalogGenerator
from toontown.toonbase import ToontownGlobals

# The catalog schedule is measured in minutes since the epoch, the same unit
# the delivery schedule uses.
CatalogWeekMinutes = 7 * 24 * 60


class CatalogManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('CatalogManagerAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        # The generator memoises its seasonal item lists per day, so there is
        # one generator for the whole district.
        self.catalogGenerator = CatalogGenerator.CatalogGenerator()

    def startCatalog(self):
        avId = self.air.getAvatarIdFromSender()
        avatar = self.air.doId2do.get(avId)
        if avatar is None:
            self.notify.warning('startCatalog from unknown avatar %s.' % avId)
            return
        if avatar.catalogScheduleNextTime != 0:
            self.notify.warning('Avatar %s already has a catalog.' % avId)
            return
        self.__issueCatalog(avatar, 0, 1)

    def deliverCatalogFor(self, avatar):
        currentWeek, nextTime = avatar.getCatalogSchedule()
        if nextTime == 0:
            # The avatar has never asked for its first catalog; the client
            # does that itself when it sees an empty schedule.
            return
        now = self.__getNow()
        if now < nextTime:
            return
        # Catch the counter up in one step, however long the avatar has been
        # away, and generate only the issue it lands on.
        weeksLate = (now - nextTime) // CatalogWeekMinutes + 1
        self.__issueCatalog(avatar, currentWeek, currentWeek + weeksLate)

    def isItemReleased(self, item):
        for itemList in self.catalogGenerator.getReleasedCatalogList(self.__getNow()):
            if item in itemList:
                return 1

        return 0

    def __issueCatalog(self, avatar, previousWeek, week):
        now = self.__getNow()
        week = (week - 1) % ToontownGlobals.CatalogNumWeeks + 1
        monthlyCatalog = self.catalogGenerator.generateMonthlyCatalog(avatar, now)
        weeklyCatalog = self.catalogGenerator.generateWeeklyCatalog(avatar, week, monthlyCatalog)
        backCatalog = self.catalogGenerator.generateBackCatalog(avatar, week, previousWeek, weeklyCatalog)
        # The catalog must be stored before the schedule: setCatalogSchedule
        # is what arms the next delivery task.
        avatar.b_setCatalog(monthlyCatalog, weeklyCatalog, backCatalog)
        avatar.b_setCatalogSchedule(week, now + CatalogWeekMinutes)
        avatar.b_setCatalogNotify(ToontownGlobals.NewItems, avatar.mailboxNotify)

    def __getNow(self):
        return int(time.time() / 60 + 0.5)
