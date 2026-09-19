import math

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.building import DoorTypes
from toontown.estate import CannonGlobals
from toontown.estate.DistributedCannonAI import DistributedCannonAI
from toontown.estate.DistributedTargetAI import DistributedTargetAI
from toontown.estate.DistributedHouseDoorAI import DistributedHouseDoorAI
from toontown.estate.DistributedHouseInteriorAI import DistributedHouseInteriorAI
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
        self.cannon = None
        self.target = None
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

    def createCannon(self, estateAI):
        """Generate this house's pinball cannon and the target it shoots at,
        if the house has one (`cannonEnabled`, etc/toon.dc:1219).  Both go in
        the estate's outdoor zone.  The
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

    def destroy(self):
        self.destroyCannon()
        for distObj in (self.insideDoor, self.door, self.interior):
            if distObj is not None:
                distObj.requestDelete()

        self.insideDoor = None
        self.door = None
        self.interior = None
        if self.interiorZoneId is not None:
            self.air.deallocateZone(self.interiorZoneId)
            self.interiorZoneId = None

        self.requestDelete()
