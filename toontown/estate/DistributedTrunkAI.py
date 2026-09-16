from direct.directnotify import DirectNotifyGlobal
from direct.task.Task import Task

from toontown.estate import ClosetGlobals
from toontown.estate.DistributedClosetAI import DistributedClosetAI
from toontown.toon import ToonDNA


class DistributedTrunkAI(DistributedClosetAI):
    """One accessory session at a time, over the toon's hat/glasses/
    backpack/shoes lists rather than the closet's two clothes lists
    (etc/toon.dc:2147-2152, DistributedTrunk.py:13).
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTrunkAI')

    _FAMILIES = {
        ToonDNA.HAT: ('getHatList', 'b_setHatList', 'b_setHat'),
        ToonDNA.GLASSES: ('getGlassesList', 'b_setGlassesList', 'b_setGlasses'),
        ToonDNA.BACKPACK: ('getBackpackList', 'b_setBackpackList', 'b_setBackpack'),
        ToonDNA.SHOES: ('getShoesList', 'b_setShoesList', 'b_setShoes'),
    }

    def __init__(self, air, furnitureMgr, item, interiorIndex=None):
        DistributedClosetAI.__init__(self, air, furnitureMgr, item,
                                     interiorIndex=interiorIndex)
        self.hatList = []
        self.glassesList = []
        self.backpackList = []
        self.shoesList = []
        self.entryHat = (0, 0, 0)
        self.entryGlasses = (0, 0, 0)
        self.entryBackpack = (0, 0, 0)
        self.entryShoes = (0, 0, 0)

    def enterAvatar(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('enterAvatar from unknown avatar: %s' % avId)
            return
        if self.isBusy():
            self.freeAvatar(avId)
            return

        self.customerId = avId
        self.entryHat = av.getHat()
        self.entryGlasses = av.getGlasses()
        self.entryBackpack = av.getBackpack()
        self.entryShoes = av.getShoes()
        self.hatList = list(av.getHatList())
        self.glassesList = list(av.getGlassesList())
        self.backpackList = list(av.getBackpackList())
        self.shoesList = list(av.getShoesList())
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleUnexpectedExit, extraArgs=[avId])
        self.doMethodLater(ClosetGlobals.TIMEOUT_TIME, self.__handleTimeout,
                           self.uniqueName('clearMovie'))
        self.d_setState(ClosetGlobals.OPEN, avId, self.ownerId,
                        av.getStyle().gender, self.hatList, self.glassesList,
                        self.backpackList, self.shoesList)

    def setDNA(self, hatIdx, hatTexture, hatColor, glassesIdx, glassesTexture,
              glassesColor, backpackIdx, backpackTexture, backpackColor,
              shoesIdx, shoesTexture, shoesColor, finished, which):
        avId = self.air.getAvatarIdFromSender()
        av = self.__customer(avId, 'setDNA')
        if av is None:
            return

        if finished == 0:
            # a live preview for everyone else in the room, same as the
            # closet's own finished == 0 (DistributedCloset.py:295-296)
            self.d_setCustomerDNA(avId, hatIdx, hatTexture, hatColor,
                                  glassesIdx, glassesTexture, glassesColor,
                                  backpackIdx, backpackTexture, backpackColor,
                                  shoesIdx, shoesTexture, shoesColor, which)
            return

        if finished == 1:
            av.b_setHat(*self.entryHat)
            av.b_setGlasses(*self.entryGlasses)
            av.b_setBackpack(*self.entryBackpack)
            av.b_setShoes(*self.entryShoes)
            self.__release(ClosetGlobals.CLOSET_MOVIE_COMPLETE)
            return

        values = {
            ToonDNA.HAT: (hatIdx, hatTexture, hatColor),
            ToonDNA.GLASSES: (glassesIdx, glassesTexture, glassesColor),
            ToonDNA.BACKPACK: (backpackIdx, backpackTexture, backpackColor),
            ToonDNA.SHOES: (shoesIdx, shoesTexture, shoesColor),
        }
        for bit, value in values.items():
            if not which & bit:
                continue
            if not av.isValidAccessorySetting(bit, *value):
                self.__reject(avId, 'trunk dna names an unowned accessory (family %d)' % bit)
                return

        for bit, value in values.items():
            if which & bit:
                setter = getattr(av, self._FAMILIES[bit][2])
                setter(*value)

        self.d_setCustomerDNA(avId, hatIdx, hatTexture, hatColor,
                              glassesIdx, glassesTexture, glassesColor,
                              backpackIdx, backpackTexture, backpackColor,
                              shoesIdx, shoesTexture, shoesColor, which)
        self.__release(ClosetGlobals.CLOSET_MOVIE_COMPLETE)

    def removeItem(self, idx, texture, colour, which):
        avId = self.air.getAvatarIdFromSender()
        av = self.__customer(avId, 'removeItem')
        if av is None:
            return

        family = self._FAMILIES.get(which)
        if family is None:
            self.__reject(avId, 'removeItem names an unknown trunk family: %s' % which)
            self.d_resetItemLists()
            return
        getListName, bSetListName, _ = family
        # the client only offers the trash can while it has a replacement
        # to swap to (DistributedTrunk.py:271-280); do not trust it
        if len(getattr(av, getListName)()) <= 3:
            self.d_resetItemLists()
            return
        if not av.removeItemInAccessoriesList(which, idx, texture, colour):
            self.d_resetItemLists()
            return
        getattr(av, bSetListName)(getattr(av, getListName)())

    def d_setState(self, mode, avId, ownerId, gender, hatList, glassesList,
                   backpackList, shoesList):
        self.sendUpdate('setState', [mode, avId, ownerId, gender,
                                     hatList, glassesList, backpackList,
                                     shoesList])

    def d_setCustomerDNA(self, avId, hatIdx, hatTexture, hatColor, glassesIdx,
                         glassesTexture, glassesColor, backpackIdx,
                         backpackTexture, backpackColor, shoesIdx,
                         shoesTexture, shoesColor, which):
        self.sendUpdate('setCustomerDNA', [avId, hatIdx, hatTexture, hatColor,
                                           glassesIdx, glassesTexture, glassesColor,
                                           backpackIdx, backpackTexture, backpackColor,
                                           shoesIdx, shoesTexture, shoesColor, which])

    def __customer(self, avId, what):
        if avId != self.customerId:
            self.__reject(avId, '%s for a trunk session belonging to %s'
                          % (what, self.customerId))
            return None
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('%s from unknown avatar: %s' % (what, avId))
            return None
        return av

    def __reject(self, avId, reason):
        self.notify.warning('%s: %s' % (avId, reason))
        self.air.writeServerEvent('suspicious', avId, reason)

    def __release(self, mode):
        avId = self.customerId
        self.__stopTimeout()
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.customerId = 0
        self.entryHat = (0, 0, 0)
        self.entryGlasses = (0, 0, 0)
        self.entryBackpack = (0, 0, 0)
        self.entryShoes = (0, 0, 0)
        self.d_setMovie(mode, avId)
        if mode != ClosetGlobals.CLOSET_MOVIE_CLEAR:
            # leave the required field idle once the movie plays out, so a
            # later generate (the avatar re-entering the house) replays a
            # mode every client ignores instead of the terminal one
            self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_CLEAR, avId)
        self.d_setState(ClosetGlobals.CLOSED, avId, self.ownerId, '', [], [], [], [])
        if avId in self.air.doId2do:
            self.freeAvatar(avId)

    def __stopTimeout(self):
        self.removeTask(self.uniqueName('clearMovie'))

    def __handleTimeout(self, task):
        self.notify.debug('trunk session for %s timed out' % self.customerId)
        self.__release(ClosetGlobals.CLOSET_MOVIE_TIMEOUT)
        return Task.done

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar %s exited unexpectedly' % avId)
        if self.customerId != avId:
            return
        self.__release(ClosetGlobals.CLOSET_MOVIE_CLEAR)
