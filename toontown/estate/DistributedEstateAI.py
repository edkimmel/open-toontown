import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import HouseGlobals
from toontown.estate.EstateProvisioner import NUM_HOUSE_SLOTS, fieldValue


class DistributedEstateAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedEstateAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.estateType = 0
        self.dawnTime = 0
        self.clouds = 0
        self.decorData = []
        self.lastEpochTimeStamp = 0
        self.rentalTimeStamp = 0
        self.rentalType = 0
        self.slotToonIds = [0] * NUM_HOUSE_SLOTS
        self.slotItems = [[] for _ in range(NUM_HOUSE_SLOTS)]
        self.idList = [0] * NUM_HOUSE_SLOTS
        self._idListLive = False

    def announceGenerate(self):
        # setIdList (etc/toon.dc:1196) is the only wire copy of slotToonIds --
        # DistributedLawnDecor.getOwnerId (DistributedLawnDecor.py:216-222)
        # indexes estate.idList by ownerIndex, the same index
        # DistributedLawnDecorAI.getOwnerAvId uses into slotToonIds
        # (DistributedLawnDecorAI.py:60-63).  slotToonIds is already final by
        # the time announceGenerate runs (required fields are unpacked before
        # generate()/announceGenerate()), so this is the first safe point to
        # broadcast it.
        DistributedObjectAI.announceGenerate(self)
        self._idListLive = True
        self.b_setIdList(list(self.slotToonIds))
        # setTreasureIds (etc/toon.dc:1175) is the only thing that creates
        # estate.flyingTreasureId (DistributedEstate.py:233-236), which
        # DistributedCannon.__calcHitTreasures (DistributedCannon.py:1255)
        # reads unconditionally on every cannon fire.  No estate treasure
        # planner exists in this codebase, so there are never any flying
        # treasure doIds to report; send the empty list so the attribute
        # always exists by the time a cannon can be fired.
        self.d_setTreasureIds([])

    def getIdList(self):
        return self.idList

    def setIdList(self, idList):
        self.idList = idList

    def b_setIdList(self, idList):
        self.setIdList(idList)
        self.d_setIdList(idList)

    def d_setIdList(self, idList):
        self.sendUpdate('setIdList', [idList])

    def d_setTreasureIds(self, doIds):
        self.sendUpdate('setTreasureIds', [doIds])

    def loadFromDb(self, fields):
        fields = fields or {}
        self.estateType = fieldValue(fields, 'setEstateType', self.estateType)
        self.decorData = fieldValue(fields, 'setDecorData', self.decorData)
        self.lastEpochTimeStamp = fieldValue(fields, 'setLastEpochTimeStamp', self.lastEpochTimeStamp)
        self.rentalTimeStamp = fieldValue(fields, 'setRentalTimeStamp', self.rentalTimeStamp)
        self.rentalType = fieldValue(fields, 'setRentalType', self.rentalType)
        for slot in range(NUM_HOUSE_SLOTS):
            self.slotToonIds[slot] = fieldValue(fields, 'setSlot%dToonId' % slot, 0)
            self.slotItems[slot] = fieldValue(fields, 'setSlot%dItems' % slot, [])

    def setEstateType(self, estateType):
        self.estateType = estateType

    def getEstateType(self):
        return self.estateType

    def setDawnTime(self, dawnTime):
        self.dawnTime = dawnTime

    def getDawnTime(self):
        return self.dawnTime

    def setClouds(self, clouds):
        self.clouds = clouds

    def getClouds(self):
        return self.clouds

    def setDecorData(self, decorData):
        self.decorData = decorData

    def getDecorData(self):
        return self.decorData

    def setLastEpochTimeStamp(self, timeStamp):
        self.lastEpochTimeStamp = timeStamp

    def getLastEpochTimeStamp(self):
        return self.lastEpochTimeStamp

    def b_setLastEpochTimeStamp(self, timeStamp):
        self.setLastEpochTimeStamp(timeStamp)
        self.d_setLastEpochTimeStamp(timeStamp)

    def d_setLastEpochTimeStamp(self, timeStamp):
        # required airecv db, same push-to-db pattern as d_setSlotItems.
        self.sendUpdate('setLastEpochTimeStamp', [timeStamp])

    def setRentalTimeStamp(self, timeStamp):
        self.rentalTimeStamp = timeStamp

    def getRentalTimeStamp(self):
        return self.rentalTimeStamp

    def setRentalType(self, rentalType):
        self.rentalType = rentalType

    def getRentalType(self):
        return self.rentalType

    def _setSlotToonId(self, slot, avId):
        self.slotToonIds[slot] = avId
        if self._idListLive:
            self.b_setIdList(list(self.slotToonIds))

    def setSlot0ToonId(self, avId):
        self._setSlotToonId(0, avId)

    def getSlot0ToonId(self):
        return self.slotToonIds[0]

    def setSlot0Items(self, items):
        self.slotItems[0] = items

    def getSlot0Items(self):
        return self.slotItems[0]

    def setSlot1ToonId(self, avId):
        self._setSlotToonId(1, avId)

    def getSlot1ToonId(self):
        return self.slotToonIds[1]

    def setSlot1Items(self, items):
        self.slotItems[1] = items

    def getSlot1Items(self):
        return self.slotItems[1]

    def setSlot2ToonId(self, avId):
        self._setSlotToonId(2, avId)

    def getSlot2ToonId(self):
        return self.slotToonIds[2]

    def setSlot2Items(self, items):
        self.slotItems[2] = items

    def getSlot2Items(self):
        return self.slotItems[2]

    def setSlot3ToonId(self, avId):
        self._setSlotToonId(3, avId)

    def getSlot3ToonId(self):
        return self.slotToonIds[3]

    def setSlot3Items(self, items):
        self.slotItems[3] = items

    def getSlot3Items(self):
        return self.slotItems[3]

    def setSlot4ToonId(self, avId):
        self._setSlotToonId(4, avId)

    def getSlot4ToonId(self):
        return self.slotToonIds[4]

    def setSlot4Items(self, items):
        self.slotItems[4] = items

    def getSlot4Items(self):
        return self.slotItems[4]

    def setSlot5ToonId(self, avId):
        self._setSlotToonId(5, avId)

    def getSlot5ToonId(self):
        return self.slotToonIds[5]

    def setSlot5Items(self, items):
        self.slotItems[5] = items

    def getSlot5Items(self):
        return self.slotItems[5]

    def b_setSlotItems(self, slot, items):
        getattr(self, 'setSlot%dItems' % slot)(items)
        self.d_setSlotItems(slot, items)

    def d_setSlotItems(self, slot, items):
        # setSlotNItems has no broadcast keyword (etc/toon.dc:1185-1195), but
        # sendUpdate is still how an AI pushes a `db` field to the database --
        # the same pattern DistributedToonAI.d_setInventory uses for the
        # equally broadcast-less setInventory (etc/toon.dc:460).
        self.sendUpdate('setSlot%dItems' % slot, [items])

    def requestServerTime(self):
        avId = self.air.getAvatarIdFromSender()
        serverTime = int(time.time() % HouseGlobals.DAY_NIGHT_PERIOD)
        self.sendUpdateToAvatarId(avId, 'setServerTime', [serverTime])
