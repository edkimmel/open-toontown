from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.building import DoorTypes
from toontown.catalog import CatalogItem
from toontown.catalog import CatalogItemList
from toontown.estate.DistributedFurnitureManagerAI import DistributedFurnitureManagerAI
from toontown.estate.DistributedHouseDoorAI import DistributedHouseDoorAI
from toontown.estate.DistributedHouseInteriorAI import DistributedHouseInteriorAI
from toontown.estate.DistributedMailboxAI import DistributedMailboxAI
from toontown.estate.EstateProvisioner import fieldValue


class DistributedHouseAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedHouseAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.housePos = 0
        self.houseType = 0
        self.gardenPos = 0
        self.avatarId = 0
        self.name = ''
        self.color = 0
        self.atticItems = b''
        self.interiorItems = b''
        self.atticWallpaper = b''
        self.interiorWallpaper = b''
        self.atticWindows = b''
        self.interiorWindows = b''
        self.deletedItems = b''
        self.cannonEnabled = 0
        self.interiorZoneId = None
        self.interior = None
        self.furnitureMgr = None
        self.mailbox = None
        self.door = None
        self.insideDoor = None

    def loadFromDb(self, fields):
        fields = fields or {}
        self.houseType = fieldValue(fields, 'setHouseType', self.houseType)
        self.gardenPos = fieldValue(fields, 'setGardenPos', self.gardenPos)
        self.avatarId = fieldValue(fields, 'setAvatarId', self.avatarId)
        self.name = fieldValue(fields, 'setName', self.name)
        self.color = fieldValue(fields, 'setColor', self.color)
        self.atticItems = fieldValue(fields, 'setAtticItems', self.atticItems)
        self.interiorItems = fieldValue(fields, 'setInteriorItems', self.interiorItems)
        self.atticWallpaper = fieldValue(fields, 'setAtticWallpaper', self.atticWallpaper)
        self.interiorWallpaper = fieldValue(fields, 'setInteriorWallpaper', self.interiorWallpaper)
        self.atticWindows = fieldValue(fields, 'setAtticWindows', self.atticWindows)
        self.interiorWindows = fieldValue(fields, 'setInteriorWindows', self.interiorWindows)
        self.deletedItems = fieldValue(fields, 'setDeletedItems', self.deletedItems)

    def setHousePos(self, housePos):
        self.housePos = housePos

    def getHousePos(self):
        return self.housePos

    def setHouseType(self, houseType):
        self.houseType = houseType

    def getHouseType(self):
        return self.houseType

    def setGardenPos(self, gardenPos):
        self.gardenPos = gardenPos

    def getGardenPos(self):
        return self.gardenPos

    def setAvatarId(self, avatarId):
        self.avatarId = avatarId

    def getAvatarId(self):
        return self.avatarId

    def setName(self, name):
        self.name = name

    def getName(self):
        return self.name

    def setColor(self, color):
        self.color = color

    def getColor(self):
        return self.color

    def setAtticItems(self, items):
        self.atticItems = items

    def getAtticItems(self):
        return self.atticItems

    def setInteriorItems(self, items):
        self.interiorItems = items

    def getInteriorItems(self):
        return self.interiorItems

    def setAtticWallpaper(self, wallpaper):
        self.atticWallpaper = wallpaper

    def getAtticWallpaper(self):
        return self.atticWallpaper

    def setInteriorWallpaper(self, wallpaper):
        self.interiorWallpaper = wallpaper

    def getInteriorWallpaper(self):
        return self.interiorWallpaper

    def setAtticWindows(self, windows):
        self.atticWindows = windows

    def getAtticWindows(self):
        return self.atticWindows

    def setInteriorWindows(self, windows):
        self.interiorWindows = windows

    def getInteriorWindows(self):
        return self.interiorWindows

    def setDeletedItems(self, items):
        self.deletedItems = items

    def getDeletedItems(self):
        return self.deletedItems

    def setCannonEnabled(self, enabled):
        self.cannonEnabled = enabled

    def getCannonEnabled(self):
        return self.cannonEnabled

    def getInteriorItemList(self):
        """The items standing in the room keep their placement, unlike the
        ones in the attic (toontown/estate/DistributedFurnitureManager.py:50)."""
        return CatalogItemList.CatalogItemList(
            self.interiorItems, store=CatalogItem.Customization | CatalogItem.Location)

    def setInteriorItemList(self, items):
        self.interiorItems = items.getBlob(
            store=CatalogItem.Customization | CatalogItem.Location)

    def getAtticItemList(self):
        return CatalogItemList.CatalogItemList(
            self.atticItems, store=CatalogItem.Customization)

    def addAtticItem(self, item):
        """CatalogFurnitureItem.recordPurchase calls this to deliver a
        purchase into the attic (toontown/catalog/CatalogFurnitureItem.py:1032)."""
        items = self.getAtticItemList()
        items.append(item)
        self.setAtticItems(items.getBlob())

    def getAtticWallpaperList(self):
        return CatalogItemList.CatalogItemList(
            self.atticWallpaper, store=CatalogItem.Customization)

    def getAtticWindowList(self):
        return CatalogItemList.CatalogItemList(
            self.atticWindows, store=CatalogItem.Customization)

    def getDeletedItemList(self):
        return CatalogItemList.CatalogItemList(
            self.deletedItems, store=CatalogItem.Customization)

    def getNumHouseItems(self):
        """The count the catalog compares against MaxHouseItems, computed the
        way toontown/catalog/CatalogAtticItem.py:24-26 computes it."""
        count = 0
        for blob in (self.atticItems, self.atticWallpaper, self.atticWindows):
            count += len(CatalogItemList.CatalogItemList(
                blob, store=CatalogItem.Customization))

        return count + len(self.getInteriorItemList())

    def d_setHouseReady(self):
        self.sendUpdate('setHouseReady', [])

    def createInterior(self):
        """Generate this house's interior and its door pair, the same shape
        toontown/building/DistributedBuildingAI.py:413-428 uses for a toon
        building: the exterior door lives with the house, the interior door
        with the interior."""
        exteriorZoneId = self.zoneId
        self.interiorZoneId = self.air.allocateZone(owner=self.avatarId)
        self.interior = DistributedHouseInteriorAI(self.air, self.doId, self.housePos,
                                                   self.interiorWallpaper,
                                                   self.interiorWindows)
        self.interior.generateWithRequired(self.interiorZoneId)
        door = DistributedHouseDoorAI(self.air, self.doId, DoorTypes.EXT_STANDARD)
        insideDoor = DistributedHouseDoorAI(self.air, self.doId, DoorTypes.INT_STANDARD)
        door.setOtherDoor(insideDoor)
        insideDoor.setOtherDoor(door)
        door.zoneId = exteriorZoneId
        insideDoor.zoneId = self.interiorZoneId
        door.generateWithRequired(exteriorZoneId)
        insideDoor.generateWithRequired(self.interiorZoneId)
        self.door = door
        self.insideDoor = insideDoor
        self.furnitureMgr = DistributedFurnitureManagerAI(self.air, self, self.interior)
        self.furnitureMgr.generateWithRequired(self.interiorZoneId)
        self.furnitureMgr.createFurniture(self.interiorZoneId)

    def createMailbox(self):
        self.mailbox = DistributedMailboxAI(self.air, self)
        self.mailbox.generateWithRequired(self.zoneId)

    def destroy(self):
        if self.furnitureMgr is not None:
            self.furnitureMgr.destroy()
            self.furnitureMgr = None
        for distObj in (self.mailbox, self.insideDoor, self.door, self.interior):
            if distObj is not None:
                distObj.requestDelete()

        self.mailbox = None
        self.insideDoor = None
        self.door = None
        self.interior = None
        if self.interiorZoneId is not None:
            self.air.deallocateZone(self.interiorZoneId)
            self.interiorZoneId = None

        self.requestDelete()
