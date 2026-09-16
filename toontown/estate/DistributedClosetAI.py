from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.task.Task import Task

from toontown.estate import ClosetGlobals
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.toon import ToonDNA


class DistributedClosetAI(DistributedFurnitureItemAI):
    """One clothes-changing session at a time.

    The closet stores no garments: the wardrobe lives on the toon
    (setClothesTopsList/setClothesBottomsList, etc/toon.dc:472-473), so this
    is a validator over the customer's own fields.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedClosetAI')

    def __init__(self, air, furnitureMgr, item, interiorIndex=None):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, item,
                                            interiorIndex=interiorIndex)
        self.ownerId = furnitureMgr.getOwnerId()
        self.customerId = 0
        # the style the customer walked in with, restored on a revert and
        # used as the baseline every edit is checked against
        self.customerDNA = None
        self.topList = []
        self.botList = []

    def getOwnerId(self):
        return self.ownerId

    def setOwnerId(self, ownerId):
        self.ownerId = ownerId

    def b_setOwnerId(self, ownerId):
        self.setOwnerId(ownerId)
        self.sendUpdate('setOwnerId', [ownerId])

    def delete(self):
        self.__stopTimeout()
        self.ignoreAll()
        self.customerId = 0
        self.customerDNA = None
        DistributedFurnitureItemAI.delete(self)

    def isBusy(self):
        return self.customerId != 0

    def enterAvatar(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('enterAvatar from unknown avatar: %s' % avId)
            return
        if self.isBusy():
            # the client has already put the toon into the closet state, so an
            # unanswered enterAvatar leaves it stuck there
            # (toontown/estate/DistributedCloset.py:196-199)
            self.freeAvatar(avId)
            return

        self.customerId = avId
        self.customerDNA = ToonDNA.ToonDNA()
        self.customerDNA.makeFromNetString(av.getDNAString())
        self.topList = list(av.getClothesTopsList())
        self.botList = list(av.getClothesBottomsList())
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleUnexpectedExit, extraArgs=[avId])
        self.doMethodLater(ClosetGlobals.TIMEOUT_TIME, self.__handleTimeout,
                           self.uniqueName('clearMovie'))
        self.d_setState(ClosetGlobals.OPEN, avId, self.ownerId,
                        self.customerDNA.gender, self.topList, self.botList)

    def setDNA(self, blob, finished, whichItems):
        avId = self.air.getAvatarIdFromSender()
        av = self.__customer(avId, 'setDNA')
        if av is None:
            return

        dna = ToonDNA.ToonDNA()
        if not dna.isValidNetString(bytes(blob)):
            self.__reject(avId, 'invalid closet dna')
            return
        dna.makeFromNetString(bytes(blob))
        if not self.__isGarmentChange(dna):
            self.__reject(avId, 'closet dna changes more than clothes')
            return

        if finished == 0:
            # a live preview for everyone else in the room
            # (DistributedCloset.py:295-296,363-374)
            self.d_setCustomerDNA(avId, dna.makeNetString())
            return

        if finished == 1:
            # the client timed out or cancelled and sent back its entry style
            # (DistributedCloset.py:348-350)
            av.b_setDNAString(self.customerDNA.makeNetString())
            self.__release(ClosetGlobals.CLOSET_MOVIE_COMPLETE)
            return

        if not self.__ownsGarments(av, dna, whichItems):
            self.__reject(avId, 'closet dna names an unowned garment')
            return

        style = self.__applySlots(dna, whichItems)
        av.b_setDNAString(style.makeNetString())
        self.d_setCustomerDNA(avId, style.makeNetString())
        self.__release(ClosetGlobals.CLOSET_MOVIE_COMPLETE)

    def removeItem(self, blob, t_or_b):
        avId = self.air.getAvatarIdFromSender()
        av = self.__customer(avId, 'removeItem')
        if av is None:
            return

        dna = ToonDNA.ToonDNA()
        if not dna.isValidNetString(bytes(blob)):
            self.__reject(avId, 'invalid closet trash dna')
            self.d_resetItemLists()
            return
        dna.makeFromNetString(bytes(blob))

        if t_or_b == ClosetGlobals.SHIRT:
            # the client only offers the trash can while it has a replacement
            # to swap to (DistributedCloset.py:319); do not trust it
            if len(av.getClothesTopsList()) <= 4:
                self.d_resetItemLists()
                return
            if not av.removeItemInClothesTopsList(dna.topTex, dna.topTexColor,
                                                  dna.sleeveTex, dna.sleeveTexColor):
                self.d_resetItemLists()
                return
            av.b_setClothesTopsList(av.getClothesTopsList())
        else:
            if len(av.getClothesBottomsList()) <= 2:
                self.d_resetItemLists()
                return
            if not av.removeItemInClothesBottomsList(dna.botTex, dna.botTexColor):
                self.d_resetItemLists()
                return
            av.b_setClothesBottomsList(av.getClothesBottomsList())

    def d_setState(self, mode, avId, ownerId, gender, topList, botList):
        self.sendUpdate('setState', [mode, avId, ownerId, gender,
                                     topList, botList])

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId,
                                     globalClockDelta.getRealNetworkTime(bits=32)])

    def d_setCustomerDNA(self, avId, dnaString):
        self.sendUpdate('setCustomerDNA', [avId, dnaString])

    def d_resetItemLists(self):
        self.sendUpdate('resetItemLists', [])

    def freeAvatar(self, avId):
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])

    def __customer(self, avId, what):
        """The avatar whose session this is, or None once the request has been
        answered with a suspicious event."""
        if avId != self.customerId:
            self.__reject(avId, '%s for a closet session belonging to %s'
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

    def __isGarmentChange(self, dna):
        """True when `dna` differs from the entry style in clothes only.  The
        torso's second character is part of the wardrobe -- a skirt and a pair
        of shorts are different torsos (ToonDNA.py:168-176), which is why the
        client reacts to it in setCustomerDNA (DistributedCloset.py:366-370).
        """
        old = self.customerDNA
        if old is None:
            return False
        return (dna.head == old.head and dna.legs == old.legs
                and dna.gender == old.gender and dna.torso[0] == old.torso[0]
                and dna.armColor == old.armColor
                and dna.gloveColor == old.gloveColor
                and dna.legColor == old.legColor
                and dna.headColor == old.headColor)

    def __ownsGarments(self, av, dna, whichItems):
        old = self.customerDNA
        if whichItems & ClosetGlobals.SHIRT:
            top = (dna.topTex, dna.topTexColor, dna.sleeveTex, dna.sleeveTexColor)
            if top != (old.topTex, old.topTexColor, old.sleeveTex, old.sleeveTexColor):
                if not self.__inList(av.getClothesTopsList(), top, 4):
                    return False
        if whichItems & ClosetGlobals.SHORTS:
            bottom = (dna.botTex, dna.botTexColor)
            if bottom != (old.botTex, old.botTexColor):
                if not self.__inList(av.getClothesBottomsList(), bottom, 2):
                    return False
        return True

    def __inList(self, clothesList, garment, stride):
        for i in range(0, len(clothesList) - stride + 1, stride):
            if tuple(clothesList[i:i + stride]) == garment:
                return True
        return False

    def __applySlots(self, dna, whichItems):
        """The entry style with only the slots the client says it changed
        taken from `dna` (DistributedCloset.py:352-358)."""
        style = ToonDNA.ToonDNA()
        style.makeFromNetString(self.customerDNA.makeNetString())
        if whichItems & ClosetGlobals.SHIRT:
            style.topTex = dna.topTex
            style.topTexColor = dna.topTexColor
            style.sleeveTex = dna.sleeveTex
            style.sleeveTexColor = dna.sleeveTexColor
        if whichItems & ClosetGlobals.SHORTS:
            style.torso = dna.torso
            style.botTex = dna.botTex
            style.botTexColor = dna.botTexColor
        return style

    def __release(self, mode):
        avId = self.customerId
        self.__stopTimeout()
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.customerId = 0
        self.customerDNA = None
        self.topList = []
        self.botList = []
        self.d_setMovie(mode, avId)
        self.d_setState(ClosetGlobals.CLOSED, avId, self.ownerId, '', [], [])
        if avId in self.air.doId2do:
            self.freeAvatar(avId)

    def __stopTimeout(self):
        self.removeTask(self.uniqueName('clearMovie'))

    def __handleTimeout(self, task):
        self.notify.debug('closet session for %s timed out' % self.customerId)
        self.__release(ClosetGlobals.CLOSET_MOVIE_TIMEOUT)
        return Task.done

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar %s exited unexpectedly' % avId)
        if self.customerId != avId:
            return
        self.__release(ClosetGlobals.CLOSET_MOVIE_CLEAR)
