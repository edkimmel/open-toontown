from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import GardenGlobals


class DistributedLawnDecorAI(DistributedObjectAI):
    """One garden interaction at a time, gated to the item's owner.

    Ownership is `setOwnerIndex` (etc/toon.dc:2679), an index into the
    owning estate's own slot-to-avatar mapping
    (DistributedEstateAI.py:22,78-148), the same lookup the client does
    through `getOwnerId` (DistributedLawnDecor.py:216-222).  The session
    mirrors DistributedPhoneAI's busy/__release/__handleUnexpectedExit
    shape (DistributedPhoneAI.py:45-71,217-239); this dclass has no
    `freeAvatar`, so a refusal is `interactionDenied(avId)` instead
    (etc/toon.dc:2684).
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedLawnDecorAI')

    def __init__(self, air, estateAI):
        DistributedObjectAI.__init__(self, air)
        self.estateAI = estateAI
        self.plot = 0
        self.heading = 0
        self.position = (0, 0, 0)
        self.ownerIndex = -1
        self.busy = 0

    def delete(self):
        self.ignoreAll()
        self.busy = 0
        DistributedObjectAI.delete(self)

    def setPlot(self, plot):
        self.plot = plot

    def getPlot(self):
        return self.plot

    def setHeading(self, heading):
        self.heading = heading

    def getHeading(self):
        return self.heading

    def setPosition(self, x, y, z):
        self.position = (x, y, z)

    def getPosition(self):
        return self.position

    def setOwnerIndex(self, index):
        self.ownerIndex = index

    def getOwnerIndex(self):
        return self.ownerIndex

    def getOwnerAvId(self):
        slotToonIds = self.estateAI.slotToonIds
        if 0 <= self.ownerIndex < len(slotToonIds):
            return slotToonIds[self.ownerIndex]
        return 0

    def isBusy(self):
        return self.busy != 0

    def plotEntered(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.getOwnerAvId() or self.isBusy():
            self.sendUpdate('interactionDenied', [avId])
            return
        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleUnexpectedExit, extraArgs=[avId])
        self.d_setMovie(GardenGlobals.MOVIE_CLEAR, avId)

    def removeItem(self):
        # Like `waterPlant` (DistributedPlantBaseAI, B5), `removeItem` has no
        # `plotEntered` session to check either -- every subclass overrides
        # `handleEnterPlot` and none of them call the base version that sends
        # `plotEntered` (DistributedPlantBase.py:88-89, DistributedStatuary.
        # py:87-93, DistributedGardenPlot.py:85-88, DistributedGardenBox.py:
        # 50-51), so `handleRemove`/`doPicking` send `removeItem` directly,
        # gated only by ownership (DistributedLawnDecor.canBePicked,
        # DistributedLawnDecor.py:224-231).
        avId = self.air.getAvatarIdFromSender()
        if avId != self.getOwnerAvId():
            self.notify.debug('removeItem refused for %s' % avId)
            return
        self.d_setMovie(GardenGlobals.MOVIE_REMOVE, avId)
        self._removeFromGarden()

    def _removeFromGarden(self):
        """The generic (no-reward) half of removal: delete this grown object
        and restore an empty `DistributedGardenPlotAI` at the same hard
        point, dropping the `lawnItem` out of the owner's estate slot list --
        the mirror image of `DistributedGardenPlotAI._replaceWithGrownObject`
        (B4).  `DistributedFlowerAI.removeItem` calls this too, after
        crediting the pick."""
        from toontown.estate.DistributedGardenPlotAI import DistributedGardenPlotAI
        plot = DistributedGardenPlotAI(self.air, self.estateAI)
        plot.setPlot(self.plot)
        plot.setPosition(*self.position)
        plot.setHeading(self.heading)
        plot.setOwnerIndex(self.ownerIndex)
        plot.generateWithRequired(self.zoneId)
        items = [item for item in self.estateAI.slotItems[self.ownerIndex]
                 if item[1] != self.plot]
        self.estateAI.b_setSlotItems(self.ownerIndex, items)
        self.requestDelete()

    def movieDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.busy:
            return
        self.__release(GardenGlobals.MOVIE_CLEAR)

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId])

    def __release(self, mode):
        avId = self.busy
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.busy = 0
        self.d_setMovie(mode, avId)

    def __handleUnexpectedExit(self, avId):
        if self.busy != avId:
            return
        self.notify.warning('avatar %s exited unexpectedly' % avId)
        self.__release(GardenGlobals.MOVIE_CLEAR)
