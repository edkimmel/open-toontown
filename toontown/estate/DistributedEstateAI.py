import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import GardenGlobals
from toontown.estate import HouseGlobals
from toontown.estate.EstateProvisioner import NUM_HOUSE_SLOTS, fieldValue
from toontown.toonbase import ToontownGlobals


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
        self.__armRentalExpiry()

    def delete(self):
        taskMgr.remove(self.__rentalTaskName())
        DistributedObjectAI.delete(self)

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

    def b_setRentalTimeStamp(self, timeStamp):
        self.setRentalTimeStamp(timeStamp)
        self.d_setRentalTimeStamp(timeStamp)

    def d_setRentalTimeStamp(self, timeStamp):
        self.sendUpdate('setRentalTimeStamp', [timeStamp])

    def setRentalType(self, rentalType):
        self.rentalType = rentalType

    def getRentalType(self):
        return self.rentalType

    def b_setRentalType(self, rentalType):
        self.setRentalType(rentalType)
        self.d_setRentalType(rentalType)

    def d_setRentalType(self, rentalType):
        self.sendUpdate('setRentalType', [rentalType])

    def rentItem(self, rentalType, durationMinutes):
        now = int(time.time())
        if rentalType == self.rentalType and self.rentalTimeStamp > now:
            # Renewing the same rental before it expires extends the
            # existing deadline instead of restarting the clock.
            base = self.rentalTimeStamp
        else:
            base = now
        self.b_setRentalType(rentalType)
        self.b_setRentalTimeStamp(base + durationMinutes * 60)
        self.__armRentalExpiry()
        if rentalType == ToontownGlobals.RentalCannon:
            self.__enableCannons()

    def forceExpireRental(self):
        """Dev hook: force the clock on the current rental to now, so it
        expires on the next __armRentalExpiry pass instead of waiting out
        the real deadline (~rental expire, MagicWordIndex.py)."""
        if self.rentalType == 0:
            return
        self.b_setRentalTimeStamp(int(time.time()))
        self.__armRentalExpiry()

    def __findWorld(self):
        """This estate's own EstateWorld, found through the estate manager's
        `worlds` map the way MagicWordIndex._residentHouse does -- the
        estate has no back-reference of its own to the houses around it."""
        from toontown.estate.EstateManagerAI import EstateManagerAI
        for do in self.air.doId2do.values():
            if isinstance(do, EstateManagerAI):
                for world in do.worlds.values():
                    if world.estate is self:
                        return world
        return None

    def __enableCannons(self):
        world = self.__findWorld()
        if world is None:
            return
        for house in world.houses:
            house.setCannonEnabled(1)
            house.createCannon(self)

    def __rentalTaskName(self):
        return 'estate-rental-expiry-%s' % self.doId

    def __armRentalExpiry(self):
        # Renewing (rentItem) or reactivating (announceGenerate) both call
        # this, so cancel any previous timer before arming the new one --
        # a rental never stacks two pending expiry tasks.
        taskMgr.remove(self.__rentalTaskName())
        if self.rentalType == 0:
            return
        remaining = self.rentalTimeStamp - int(time.time())
        if remaining <= 0:
            # The deadline already passed while the estate was unloaded --
            # the same offline catch-up rentItem's caller sees for
            # lastEpochTimeStamp -- so expire now instead of arming a
            # negative delay.
            self.__rentalExpired()
            return
        taskMgr.doMethodLater(remaining, self.__rentalExpired,
                              self.__rentalTaskName(), extraArgs=[])

    def __rentalExpired(self):
        rentalType = self.rentalType
        self.b_setRentalType(0)
        if rentalType == ToontownGlobals.RentalCannon:
            self.sendUpdate('cannonsOver', [])
        elif rentalType == ToontownGlobals.RentalGameTable:
            self.sendUpdate('gameTableOver', [])
        self._rentalTeardown(rentalType)

    def _rentalTeardown(self, rentalType):
        # RentalGameTable is stored and expired correctly but generates
        # nothing (no game-table DO exists), so there is nothing to tear
        # down for it here.
        if rentalType != ToontownGlobals.RentalCannon:
            return
        world = self.__findWorld()
        if world is None:
            return
        for house in world.houses:
            house.setCannonEnabled(0)
            house.destroyCannon()

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

    def completeFlowerSale(self, sell):
        # completeFlowerSale (etc/toon.dc:1198) is the done event from
        # FlowerSellGUI.__handleSaleDone (FlowerSellGUI.py); sell is 1 on
        # OK, 0 on cancel or on stoppedAsleep.  __updateFlowerValue prices
        # the basket client-side (FlowerSellGUI.py:45-52) purely for
        # display -- that number never reaches this method, so there is
        # nothing here to trust or distrust; the value is always
        # recomputed from the toon's own basket.
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.idList:
            self.air.writeServerEvent(
                'suspicious', avId,
                'completeFlowerSale from a toon not in this estate')
            return
        if not sell:
            return
        toon = self.air.doId2do.get(avId)
        if toon is None:
            return
        value = toon.flowerBasket.getTotalValue()
        if value:
            toon.addMoney(value)
        toon.b_setFlowerBasket([], [])
        self._checkFlowerTrophies(toon)

    def _checkFlowerTrophies(self, toon):
        # Shared by the sale path above and DistributedFlowerAI._collectFlower
        # (the pick path, where the collection actually grows) so both check
        # the same numbers.  Monotonic: a trophy id already in
        # getGardenTrophies() is never re-awarded or removed.  One
        # b_setGardenTrophies + awardedTrophy broadcast per newly earned id,
        # matching the reference client's own award dialog
        # (DistributedEstate.py:427-432).
        collection = getattr(toon, 'flowerCollection', None)
        if collection is None:
            return
        numFlowers = len(collection)
        have = list(toon.getGardenTrophies())
        for trophyId in sorted(GardenGlobals.GardenTrophyThresholds):
            if trophyId in have:
                continue
            if numFlowers < GardenGlobals.GardenTrophyThresholds[trophyId]:
                continue
            have.append(trophyId)
            toon.b_setGardenTrophies(list(have))
            self.sendUpdate('awardedTrophy', [toon.doId])
