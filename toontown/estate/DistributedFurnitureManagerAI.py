from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogFurnitureItem
from toontown.estate.DistributedPhoneAI import DistributedPhoneAI

# every house has a telephone, and it cannot be put away
# (toontown/estate/houseDesign.py:1546)
PhoneFurnitureType = 1399


class DistributedFurnitureManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureManagerAI')

    def __init__(self, air, house, interior):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.interior = interior
        self.items = []

    def getOwnerId(self):
        return self.house.getAvatarId()

    def getOwnerName(self):
        return self.house.getName()

    def getInteriorId(self):
        return self.interior.doId

    def getAtticItems(self):
        return self.house.getAtticItems()

    def getAtticWallpaper(self):
        return self.house.getAtticWallpaper()

    def getAtticWindows(self):
        return self.house.getAtticWindows()

    def getDeletedItems(self):
        return self.house.getDeletedItems()

    def createFurniture(self, zoneId):
        """Generate a distributed object for each item standing in the room.
        The items reparent themselves to the interior through this manager
        (toontown/estate/DistributedFurnitureItem.py:56-61), so the manager
        and the interior must already exist."""
        hasPhone = False
        for item in self.house.getInteriorItemList():
            if self.__isPhone(item):
                hasPhone = True
            self.__generateItem(item, zoneId)

        if not hasPhone:
            self.__generateItem(
                CatalogFurnitureItem.CatalogFurnitureItem(PhoneFurnitureType),
                zoneId)

    def destroy(self):
        for item in self.items:
            item.requestDelete()

        self.items = []
        self.requestDelete()

    def __isPhone(self, item):
        return (isinstance(item, CatalogFurnitureItem.CatalogFurnitureItem) and
                item.getFlags() & CatalogFurnitureItem.FLPhone)

    def __generateItem(self, item, zoneId):
        if self.__isPhone(item):
            distObj = DistributedPhoneAI(self.air, self, item)
        else:
            # the rest of the furniture is not interactive yet
            return None
        distObj.generateWithRequired(zoneId)
        self.items.append(distObj)
        return distObj
