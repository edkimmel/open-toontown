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
        # Avatars whose client asked for a first catalog before the avatar
        # itself had reached this AI.
        self.pendingAvIds = set()
        self.accept('avatarEntered', self.__handleAvatarEntered)

    def startCatalog(self):
        avId = self.air.getAvatarIdFromSender()
        avatar = self.air.doId2do.get(avId)
        if avatar is None:
            # The client asks as soon as it sees this manager
            # (toontown/catalog/CatalogManager.py:15-17), which is while it is
            # still in the uber zone -- before the avatar activates here.  Hold
            # the request until the avatar announces itself
            # (toontown/toon/DistributedToonAI.py:224).
            self.pendingAvIds.add(avId)
            self.acceptOnce(self.air.getAvatarExitEvent(avId),
                            self.pendingAvIds.discard, extraArgs=[avId])
            return
        self.__startCatalog(avatar)

    def __startCatalog(self, avatar):
        if avatar.catalogScheduleNextTime != 0:
            self.notify.warning('Avatar %s already has a catalog.' % avatar.doId)
            return
        self.__issueCatalog(avatar, 0, 1)

    def __handleAvatarEntered(self, avatar):
        if avatar.doId not in self.pendingAvIds:
            return
        self.pendingAvIds.discard(avatar.doId)
        self.ignore(self.air.getAvatarExitEvent(avatar.doId))
        self.__startCatalog(avatar)

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

    def advanceCatalogFor(self, avatar):
        """Issue exactly one catalog for an administrator's dev request.

        This deliberately shares ``__issueCatalog`` with normal delivery, so
        generation, wrapping, notification, and the next scheduled delivery
        stay identical to a real catalog issue.  An empty schedule is the one
        normal first issue; every established schedule advances one week.
        """
        currentWeek, nextTime = avatar.getCatalogSchedule()
        if nextTime == 0:
            self.__startCatalog(avatar)
            return 1
        nextWeek = (currentWeek % ToontownGlobals.CatalogNumWeeks) + 1
        self.__issueCatalog(avatar, currentWeek, nextWeek)
        return nextWeek

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
