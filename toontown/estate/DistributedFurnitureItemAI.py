from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedNodeAI import DistributedNodeAI

from toontown.catalog import CatalogItem
from toontown.estate import HouseGlobals


class DistributedFurnitureItemAI(DistributedNodeAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureItemAI')

    def __init__(self, air, furnitureMgr, item):
        DistributedNodeAI.__init__(self, air)
        self.furnitureMgr = furnitureMgr
        self.item = item
        self.mode = HouseGlobals.FURNITURE_MODE_OFF
        self.modeAvId = 0

    def getItem(self):
        # the client decodes this blob with store=Customization only
        # (toontown/estate/DistributedFurnitureItem.py:58)
        return [self.furnitureMgr.doId,
                self.item.getBlob(store=CatalogItem.Customization)]

    def getMode(self):
        return [self.mode, self.modeAvId]

    def announceGenerate(self):
        DistributedNodeAI.announceGenerate(self)
        posHpr = getattr(self.item, 'posHpr', None)
        if posHpr:
            self.b_setPosHpr(*posHpr)
