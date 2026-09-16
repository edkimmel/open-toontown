import math
import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.building import DoorTypes
from toontown.catalog import CatalogItem
from toontown.catalog import CatalogItemList
from toontown.estate import CannonGlobals
from toontown.estate import GardenGlobals
from toontown.estate.DistributedCannonAI import DistributedCannonAI
from toontown.estate.DistributedFlowerAI import DistributedFlowerAI
from toontown.estate.DistributedFurnitureManagerAI import DistributedFurnitureManagerAI
from toontown.estate.DistributedGagTreeAI import DistributedGagTreeAI
from toontown.estate.DistributedGardenBoxAI import DistributedGardenBoxAI
from toontown.estate.DistributedGardenPlotAI import DistributedGardenPlotAI
from toontown.estate.DistributedHouseDoorAI import DistributedHouseDoorAI
from toontown.estate.DistributedHouseInteriorAI import DistributedHouseInteriorAI
from toontown.estate.DistributedMailboxAI import DistributedMailboxAI
from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI
from toontown.estate.DistributedTargetAI import DistributedTargetAI
from toontown.estate.DistributedToonStatuaryAI import DistributedToonStatuaryAI
from toontown.estate.EstateProvisioner import fieldValue

SECONDS_PER_DAY = 24 * 60 * 60


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
        self.cannon = None
        self.target = None
        self.door = None
        self.insideDoor = None
        self.gardenBoxes = []
        self.gardenPlots = []
        self.gardenPlants = []

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

    def addWallpaper(self, item):
        """CatalogSurfaceItem.recordPurchase calls this to deliver a
        purchased wallpaper/flooring/moulding/wainscoting item into the
        attic (toontown/catalog/CatalogSurfaceItem.py:30)."""
        items = self.getAtticWallpaperList()
        items.append(item)
        self.b_setAtticWallpaper(items.getBlob())

    def getAtticWindowList(self):
        return CatalogItemList.CatalogItemList(
            self.atticWindows, store=CatalogItem.Customization)

    def addWindow(self, item):
        """CatalogWindowItem.recordPurchase calls this to deliver a
        purchased window into the attic
        (toontown/catalog/CatalogWindowItem.py:43)."""
        items = self.getAtticWindowList()
        items.append(item)
        self.b_setAtticWindows(items.getBlob())

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

    def createCannon(self, estateAI):
        """Generate this house's pinball cannon and the target it shoots at,
        if the house has one (`cannonEnabled`, etc/toon.dc:1219).  Both go in
        the estate's outdoor zone, the same zone createMailbox uses.  The
        target has to exist first: its doId is the cannon's required
        `targetId` field (etc/toon.dc:995).

        `CannonGlobals.cannonDrops` holds six placements and the reference
        never reads the table, so there is no placement policy to port; one
        drop per house slot keeps the six houses' cannons apart.  The target
        is parked CannonGlobals.TARGET_DISTANCE in front of the drop point,
        along its heading, CannonGlobals.TARGET_HEIGHT up, so every cannon
        starts out pointing at its own target.  Idempotent."""
        if not self.cannonEnabled or self.cannon is not None:
            return

        x, y, z, h, p, r = CannonGlobals.cannonDrops[self.housePos % len(CannonGlobals.cannonDrops)]
        heading = math.radians(h)
        self.target = DistributedTargetAI(self.air,
                                          x - math.sin(heading) * CannonGlobals.TARGET_DISTANCE,
                                          y + math.cos(heading) * CannonGlobals.TARGET_DISTANCE,
                                          z + CannonGlobals.TARGET_HEIGHT)
        self.target.generateWithRequired(self.zoneId)
        self.cannon = DistributedCannonAI(self.air, estateAI.doId, self.target.doId,
                                          x, y, z, h, p, r)
        self.cannon.generateWithRequired(self.zoneId)
        # the client keeps the target stashed until the state says enabled
        # (DistributedTarget.py:95-104)
        self.target.d_setState(1, 0, 0)

    def destroyCannon(self):
        """Tear down just this house's cannon/target pair -- what a rental's
        expiry needs (DistributedEstateAI._rentalTeardown), as opposed to
        destroy()'s whole-house teardown.  Boots any occupant out through
        the cannon's own FORCE_EXIT movie path first, so requestDelete never
        yanks the ride out from under whoever is in it."""
        if self.cannon is not None:
            self.cannon.forceExit()
            self.cannon.requestDelete()
            self.cannon = None
        if self.target is not None:
            self.target.requestDelete()
            self.target = None

    def createGarden(self, estateAI):
        """Generate this house's flower boxes, empty plot hard points, and
        any already-planted hard point's grown object, indexed by
        `gardenPos` (etc/toon.dc:1208, set to the house's own slot by
        EstateProvisioner.py:157) the same way the client's
        `whatCanBePlanted(ownerIndex, plot)` does (GardenGlobals.py:1277,
        DistributedGardenPlot.py:38).  A hard point already holding a
        planted `lawnItem` (struct at etc/toon.dc:1161, field order
        type/hardPoint/waterLevel/growthLevel/optional) regenerates as its
        grown-object DO (`_regeneratePlant`) instead of an empty plot.
        Idempotent: does nothing if this house's garden is already
        generated."""
        if self.gardenBoxes or self.gardenPlots or self.gardenPlants:
            return

        self._applyGrowthTick(estateAI)

        for boxIndex, (x, y, h, boxType) in enumerate(GardenGlobals.estateBoxes[self.gardenPos]):
            box = DistributedGardenBoxAI(self.air, estateAI)
            box.setPlot(boxIndex)
            box.setPosition(x, y, 0)
            box.setHeading(h)
            box.setOwnerIndex(self.gardenPos)
            box.setTypeIndex(boxType)
            box.generateWithRequired(self.zoneId)
            self.gardenBoxes.append(box)

        plantedItems = dict((item[1], item) for item in estateAI.slotItems[self.gardenPos])
        for hardPoint, (x, y, h, plantType) in enumerate(GardenGlobals.estatePlots[self.gardenPos]):
            x, y, h = self._hardPointPosHpr(x, y, h, plantType)
            item = plantedItems.get(hardPoint)
            if item is not None:
                self._regeneratePlant(estateAI, hardPoint, x, y, h, item)
                continue
            plot = DistributedGardenPlotAI(self.air, estateAI)
            plot.setPlot(hardPoint)
            plot.setPosition(x, y, 0)
            plot.setHeading(h)
            plot.setOwnerIndex(self.gardenPos)
            plot.generateWithRequired(self.zoneId)
            self.gardenPlots.append(plot)

    # No model in the box's own art (planterA/B/C/D,
    # phase_5.5/models/estate/) exposes a per-slot locator -- every hole a
    # box can hold flowers in is baked into a single unnamed "soil" mesh,
    # and neither DistributedGardenBox nor DistributedGardenPlot ever look
    # one up; the client just trusts whatever position/heading the AI puts
    # on each plot DO. So a box's later slots (>0) have no authoritative
    # world offset to mirror -- this lays them out evenly along the box's
    # own heading instead, spaced far enough apart that a shovel-radius
    # toon can stand at one slot without also touching its neighbor.
    _FLOWER_SLOT_SPACING = 2.5

    def _hardPointPosHpr(self, x, y, h, plantType):
        # Flower hard points in `estatePlots` aren't world coordinates at
        # all -- (x, y) is (box index, slot index) into this same house's
        # `estateBoxes` entry (box capacities always sum to the flower hard
        # point count, e.g. [1, 1, 3, 3, 2] -> 10), so a flower plot must
        # take its position/heading from the box it lives in instead of
        # the table's own (x, y, h). The box anchor alone only covers slot
        # 0 -- every other slot in a multi-capacity box needs its own
        # offset along the box's heading (see _FLOWER_SLOT_SPACING) so it
        # doesn't collapse onto slot 0's position.
        if plantType == GardenGlobals.FLOWER_TYPE:
            boxes = GardenGlobals.estateBoxes[self.gardenPos]
            if 0 <= x < len(boxes):
                bx, by, bh = boxes[x][:3]
                theta = math.radians(bh)
                dist = y * self._FLOWER_SLOT_SPACING
                return (bx + dist * math.cos(theta), by + dist * math.sin(theta), bh)
        return (x, y, h)

    def _regeneratePlant(self, estateAI, hardPoint, x, y, h, item):
        """Rebuild the grown-object DO a persisted `lawnItem` describes,
        the same construction `DistributedGardenPlotAI._replaceWithGrownObject`
        does at plant time, keyed by `PlantAttributes[type]['plantType']`
        (GAG_TREE_TYPE/FLOWER_TYPE/STATUARY_TYPE) and, for statuary,
        whether `type` is one of `ToonStatuaryTypeIndices` -- the same two
        checks `plantStatuary`/`plantToonStatuary` use."""
        plantType, _hardPoint, waterLevel, growthLevel, optional = item
        attrib = GardenGlobals.PlantAttributes.get(plantType, {})
        kind = attrib.get('plantType')
        if kind == GardenGlobals.FLOWER_TYPE:
            grown = DistributedFlowerAI(self.air, estateAI)
            grown.setVariety(optional)
        elif kind == GardenGlobals.GAG_TREE_TYPE:
            grown = DistributedGagTreeAI(self.air, estateAI)
        elif plantType in GardenGlobals.ToonStatuaryTypeIndices:
            grown = DistributedToonStatuaryAI(self.air, estateAI)
            grown.setOptional(optional)
        else:
            grown = DistributedStatuaryAI(self.air, estateAI)
        grown.setPlot(hardPoint)
        grown.setPosition(x, y, 0)
        grown.setHeading(h)
        grown.setOwnerIndex(self.gardenPos)
        grown.setTypeIndex(plantType)
        grown.setWaterLevel(waterLevel)
        grown.setGrowthLevel(growthLevel)
        grown.generateWithRequired(self.zoneId)
        self.gardenPlants.append(grown)

    def _applyGrowthTick(self, estateAI):
        """No day-boundary growth exists in the reference at all -- nothing
        outside DistributedPlantBase(AI)'s own setGrowthLevel/setWaterLevel
        setters ever assigns growthLevel or waterLevel.  This task adds the
        minimal one, piggybacked on the estate-wide `lastEpochTimeStamp`
        field (etc/toon.dc:1176, `required airecv db`), which the reference
        declares and loads (DistributedEstateAI.py:19,29) but never uses
        for anything.  One estate, one shared clock: every planted item
        grows/wilts by the same number of elapsed days since the garden was
        last generated.  Per elapsed day: watered (waterLevel > 0) advances
        growthLevel by one, capped at growthThresholds[2] (full bloom/
        fruiting -- reference client behavior does not change past that
        point, DistributedPlantBase.py:109-163), and spends one day of
        water; unwatered wilts growthLevel back down by one (floored at 0)
        and drains water further (floored at the type's minWaterLevel).
        Statuary has no `growthThresholds` (DistributedStatuaryAI's own
        comment) so it is skipped -- always planted fully grown.  The first
        time an estate is ever generated there is nothing to grow yet, so
        this only seeds the timestamp.  Elapsed days are capped at 60; the
        clamps make anything past that a no-op anyway, this just bounds the
        loop."""
        now = int(time.time())
        last = estateAI.getLastEpochTimeStamp()
        if last == 0:
            estateAI.b_setLastEpochTimeStamp(now)
            return
        elapsedDays = min((now - last) // SECONDS_PER_DAY, 60)
        if elapsedDays <= 0:
            return
        items = list(estateAI.slotItems[self.gardenPos])
        changed = False
        for i, (plantType, hardPoint, waterLevel, growthLevel, optional) in enumerate(items):
            attrib = GardenGlobals.PlantAttributes.get(plantType, {})
            thresholds = attrib.get('growthThresholds')
            if not thresholds:
                continue
            minLevel = attrib.get('minWaterLevel', -2)
            for _day in range(elapsedDays):
                if waterLevel > 0:
                    growthLevel = min(growthLevel + 1, thresholds[2])
                    waterLevel -= 1
                else:
                    growthLevel = max(growthLevel - 1, 0)
                    waterLevel = max(waterLevel - 1, minLevel)
            items[i] = (plantType, hardPoint, waterLevel, growthLevel, optional)
            changed = True
        if changed:
            estateAI.b_setSlotItems(self.gardenPos, items)
        estateAI.b_setLastEpochTimeStamp(last + elapsedDays * SECONDS_PER_DAY)

    def destroy(self):
        if self.furnitureMgr is not None:
            self.furnitureMgr.destroy()
            self.furnitureMgr = None
        for garden in self.gardenBoxes + self.gardenPlots + self.gardenPlants:
            garden.requestDelete()
        self.gardenBoxes = []
        self.gardenPlots = []
        self.gardenPlants = []
        self.destroyCannon()
        for distObj in (self.mailbox, self.insideDoor,
                        self.door, self.interior):
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
