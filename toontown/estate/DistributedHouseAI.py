from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.building import DoorTypes
from toontown.catalog import CatalogItem
from toontown.catalog import CatalogItemList
from toontown.estate import GardenGlobals
from toontown.estate.DistributedFurnitureManagerAI import DistributedFurnitureManagerAI
from toontown.estate.DistributedGardenBoxAI import DistributedGardenBoxAI
from toontown.estate.DistributedGardenPlotAI import DistributedGardenPlotAI
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
        self.gardenBoxes = []
        self.gardenPlots = []

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

    def b_setAtticItems(self, items):
        # setAtticItems is `required db`, not broadcast (etc/toon.dc:1212):
        # nothing subscribes to it, but the update still has to reach this
        # object's own doId for the DBSS to persist it.
        self.setAtticItems(items)
        self.sendUpdate('setAtticItems', [items])

    def setInteriorItems(self, items):
        self.interiorItems = items

    def getInteriorItems(self):
        return self.interiorItems

    def b_setInteriorItems(self, items):
        self.setInteriorItems(items)
        self.sendUpdate('setInteriorItems', [items])

    def setAtticWallpaper(self, wallpaper):
        self.atticWallpaper = wallpaper

    def getAtticWallpaper(self):
        return self.atticWallpaper

    def b_setAtticWallpaper(self, wallpaper):
        self.setAtticWallpaper(wallpaper)
        self.sendUpdate('setAtticWallpaper', [wallpaper])

    def setInteriorWallpaper(self, wallpaper):
        self.interiorWallpaper = wallpaper

    def getInteriorWallpaper(self):
        return self.interiorWallpaper

    def b_setInteriorWallpaper(self, wallpaper):
        self.setInteriorWallpaper(wallpaper)
        self.sendUpdate('setInteriorWallpaper', [wallpaper])

    def setAtticWindows(self, windows):
        self.atticWindows = windows

    def getAtticWindows(self):
        return self.atticWindows

    def b_setAtticWindows(self, windows):
        self.setAtticWindows(windows)
        self.sendUpdate('setAtticWindows', [windows])

    def setInteriorWindows(self, windows):
        self.interiorWindows = windows

    def getInteriorWindows(self):
        return self.interiorWindows

    def b_setInteriorWindows(self, windows):
        self.setInteriorWindows(windows)
        self.sendUpdate('setInteriorWindows', [windows])

    def setDeletedItems(self, items):
        self.deletedItems = items

    def getDeletedItems(self):
        return self.deletedItems

    def b_setDeletedItems(self, items):
        self.setDeletedItems(items)
        self.sendUpdate('setDeletedItems', [items])

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
        self.b_setInteriorItems(items.getBlob(
            store=CatalogItem.Customization | CatalogItem.Location))

    def getAtticItemList(self):
        return CatalogItemList.CatalogItemList(
            self.atticItems, store=CatalogItem.Customization)

    def addAtticItem(self, item):
        """CatalogFurnitureItem.recordPurchase calls this to deliver a
        purchase into the attic (toontown/catalog/CatalogFurnitureItem.py:1032)."""
        items = self.getAtticItemList()
        items.append(item)
        self.b_setAtticItems(items.getBlob())

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
        self.d_setHouseReady()

    def createMailbox(self):
        self.mailbox = DistributedMailboxAI(self.air, self)
        self.mailbox.generateWithRequired(self.zoneId)

    def createGarden(self, estateAI):
        """Generate this house's flower boxes and empty plot hard points,
        indexed by `gardenPos` (etc/toon.dc:1208, set to the house's own slot
        by EstateProvisioner.py:157) the same way the client's
        `whatCanBePlanted(ownerIndex, plot)` does (GardenGlobals.py:1277,
        DistributedGardenPlot.py:38).  A hard point already holding a planted
        `lawnItem` (struct at etc/toon.dc:1161, field order
        type/hardPoint/waterLevel/growthLevel/optional) is skipped -- planting
        replaces the plot DO with a grown one in a later task.  Idempotent:
        does nothing if this house's garden is already generated."""
        if self.gardenBoxes or self.gardenPlots:
            return

        for boxIndex, (x, y, h, boxType) in enumerate(GardenGlobals.estateBoxes[self.gardenPos]):
            box = DistributedGardenBoxAI(self.air, estateAI)
            box.setPlot(boxIndex)
            box.setPosition(x, y, 0)
            box.setHeading(h)
            box.setOwnerIndex(self.gardenPos)
            box.setTypeIndex(boxType)
            box.generateWithRequired(self.zoneId)
            self.gardenBoxes.append(box)

        plantedHardPoints = set(item[1] for item in estateAI.slotItems[self.gardenPos])
        for hardPoint, (x, y, h, plantType) in enumerate(GardenGlobals.estatePlots[self.gardenPos]):
            if hardPoint in plantedHardPoints:
                continue
            plot = DistributedGardenPlotAI(self.air, estateAI)
            plot.setPlot(hardPoint)
            plot.setPosition(x, y, 0)
            plot.setHeading(h)
            plot.setOwnerIndex(self.gardenPos)
            plot.generateWithRequired(self.zoneId)
            self.gardenPlots.append(plot)

    def destroy(self):
        if self.furnitureMgr is not None:
            self.furnitureMgr.destroy()
            self.furnitureMgr = None
        for garden in self.gardenBoxes + self.gardenPlots:
            garden.requestDelete()
        self.gardenBoxes = []
        self.gardenPlots = []
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
