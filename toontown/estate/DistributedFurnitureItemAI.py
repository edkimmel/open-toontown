from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedNodeAI import DistributedNodeAI

from toontown.catalog import CatalogItem
from toontown.estate import HouseGlobals


class DistributedFurnitureItemAI(DistributedNodeAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureItemAI')

    def __init__(self, air, furnitureMgr, item, interiorIndex=None):
        DistributedNodeAI.__init__(self, air)
        self.furnitureMgr = furnitureMgr
        self.item = item
        # this item's position in the house's interior list
        # (DistributedHouseAI.py:139-145), so a final drag can be written
        # back; None for an item with no interior-list entry, e.g. the
        # phone generated for a house that has none
        # (DistributedFurnitureManagerAI.py:134-137).
        self.interiorIndex = interiorIndex
        self.mode = HouseGlobals.FURNITURE_MODE_OFF
        self.modeAvId = 0

    def getItem(self):
        # the client decodes this blob with store=Customization only
        # (toontown/estate/DistributedFurnitureItem.py:58)
        return [self.furnitureMgr.doId,
                self.item.getBlob(store=CatalogItem.Customization)]

    def getMode(self):
        return [self.mode, self.modeAvId]

    def setMode(self, mode, avId):
        self.mode = mode
        self.modeAvId = avId

    def d_setMode(self, mode, avId):
        self.sendUpdate('setMode', [mode, avId])

    def b_setMode(self, mode, avId):
        self.setMode(mode, avId)
        self.d_setMode(mode, avId)

    def requestPosHpr(self, final, x, y, z, h, p, r, timestamp):
        # only the manager's current director, and only when that avatar is
        # also the house owner, may move an item (DistributedFurnitureManagerAI's
        # class docstring)
        avId = self.air.getAvatarIdFromSender()
        if avId != self.furnitureMgr.getDirector():
            return
        if avId != self.furnitureMgr.getOwnerId():
            return

        posHpr = (x, y, z, h, p, r)
        if final:
            self.b_setMode(HouseGlobals.FURNITURE_MODE_STOP, avId)
            self.b_setPosHpr(*posHpr)
            self.__persistPosHpr(posHpr)
        else:
            self.b_setMode(HouseGlobals.FURNITURE_MODE_START, avId)
            self.b_setPosHpr(*posHpr)

    def __persistPosHpr(self, posHpr):
        if self.interiorIndex is None:
            return
        house = self.furnitureMgr.house
        items = house.getInteriorItemList()
        if self.interiorIndex >= len(items):
            return
        entry = items[self.interiorIndex]
        entry.posHpr = posHpr
        items[self.interiorIndex] = entry
        house.setInteriorItemList(items)

    def announceGenerate(self):
        DistributedNodeAI.announceGenerate(self)
        posHpr = getattr(self.item, 'posHpr', None)
        if posHpr:
            self.b_setPosHpr(*posHpr)
