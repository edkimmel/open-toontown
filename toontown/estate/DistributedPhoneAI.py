from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.task.Task import Task

from toontown.estate import PhoneGlobals
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI

# same countdown the store clerk gives a shopper
# (toontown/toon/NPCToons.py:61)
PHONE_COUNTDOWN_TIME = 120


class DistributedPhoneAI(DistributedFurnitureItemAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPhoneAI')

    def __init__(self, air, furnitureMgr, item):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, item)
        self.initialScale = (1.0, 1.0, 1.0)
        self.busy = 0

    def getInitialScale(self):
        return self.initialScale

    def setInitialScale(self, sx, sy, sz):
        self.initialScale = (sx, sy, sz)

    def delete(self):
        self.__stopTimeout()
        self.ignoreAll()
        self.busy = 0
        DistributedFurnitureItemAI.delete(self)

    def isBusy(self):
        return self.busy > 0

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('avatarEnter from unknown avatar: %s' % avId)
            return
        if self.isBusy():
            # the client has already put the toon into the phone state, so an
            # unanswered avatarEnter leaves it stuck there
            # (toontown/estate/DistributedPhone.py:184)
            self.freeAvatar(avId)
            return
        if not self.__hasCatalog(av):
            self.d_setMovie(PhoneGlobals.PHONE_MOVIE_EMPTY, avId)
            self.freeAvatar(avId)
            return
        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleUnexpectedExit, extraArgs=[avId])
        self.doMethodLater(PHONE_COUNTDOWN_TIME, self.__handleTimeout,
                           self.uniqueName('clearMovie'))
        # setLimits must reach the shopper before the movie: the catalog
        # panels add to it while deciding whether the house is full
        # (toontown/catalog/CatalogAtticItem.py:38)
        self.sendUpdateToAvatarId(avId, 'setLimits', [self.getNumHouseItems()])
        self.d_setMovie(PhoneGlobals.PHONE_MOVIE_PICKUP, avId)

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busy != avId:
            if self.busy != 0:
                self.air.writeServerEvent('suspicious', avId, 'DistributedPhoneAI.avatarExit busy with %s' % self.busy)
                self.notify.warning('avatarExit from %s while busy with %s' % (avId, self.busy))
            return
        self.__release(PhoneGlobals.PHONE_MOVIE_HANGUP)

    def freeAvatar(self, avId):
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId,
                                     globalClockDelta.getRealNetworkTime(bits=32)])

    def getNumHouseItems(self):
        house = getattr(self.furnitureMgr, 'house', None)
        if house is None:
            return 0
        return house.getNumHouseItems()

    def __hasCatalog(self, av):
        return bool(len(av.monthlyCatalog) or len(av.weeklyCatalog) or len(av.backCatalog))

    def __release(self, mode):
        avId = self.busy
        self.__stopTimeout()
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.busy = 0
        self.d_setMovie(mode, avId)
        if avId in self.air.doId2do:
            self.freeAvatar(avId)

    def __stopTimeout(self):
        self.removeTask(self.uniqueName('clearMovie'))

    def __handleTimeout(self, task):
        self.notify.debug('phone session for %s timed out' % self.busy)
        self.__release(PhoneGlobals.PHONE_MOVIE_CLEAR)
        return Task.done

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar %s exited unexpectedly' % avId)
        if self.busy != avId:
            return
        self.__release(PhoneGlobals.PHONE_MOVIE_CLEAR)
