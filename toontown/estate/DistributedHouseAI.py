from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.building import DoorTypes
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

    def destroy(self):
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
