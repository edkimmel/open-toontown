from direct.directnotify import DirectNotifyGlobal

from toontown.estate.DistributedEstateAI import DistributedEstateAI
from toontown.estate.DistributedHouseAI import DistributedHouseAI
from toontown.estate.EstateProvisioner import NUM_HOUSE_SLOTS


def dropStaleObject(air, doId):
    """Forget a persistent object an earlier visit left behind.

    requestDelete only asks the State Server to delete the object
    (direct/distributed/AstronInternalRepository.py:572-584); the AI keeps its
    own reference until that delete comes back to handleObjExit (:301-313), and
    a visit that ended uncleanly may leave it there for good.  Generating the
    persistent doId again on top of it raises 'already in doId2do', so the
    stale object goes first -- the same thing DistributedBattleBaseAI does
    before it regenerates a pet proxy on its persistent doId
    (toontown/battle/DistributedBattleBaseAI.py:1120-1127).
    """
    do = air.doId2do.get(doId)
    if do is None:
        return

    do.requestDelete()
    air.removeDOFromTables(do)
    do.delete()


class EstateWorld:
    """One account's estate while it is live: the zone it was generated in,
    the objects generated there, and the avatars standing in it.  The estate
    and house doIds are persistent; the zone is not."""

    def __init__(self, accountId, ownerId, estateId, houseIds):
        self.accountId = accountId
        self.ownerId = ownerId
        self.estateId = estateId
        self.houseIds = list(houseIds)
        self.zoneId = None
        self.estate = None
        self.houses = []
        self.occupants = []

    def addOccupant(self, avId):
        if avId not in self.occupants:
            self.occupants.append(avId)

    def removeOccupant(self, avId):
        if avId in self.occupants:
            self.occupants.remove(avId)

    def getHouseZones(self):
        return [house.interiorZoneId for house in self.houses
                if house.interiorZoneId is not None]

    def getZones(self):
        zones = [] if self.zoneId is None else [self.zoneId]
        zones.extend(self.getHouseZones())
        return zones

    def destroy(self, air):
        for house in self.houses:
            house.destroy()

        self.houses = []
        if self.estate is not None:
            self.estate.requestDelete()
            self.estate = None

        if self.zoneId is not None:
            air.deallocateZone(self.zoneId)
            self.zoneId = None


class EstateWorldOperation:
    """Reads the persisted estate and house records, then generates them into
    a freshly allocated zone."""

    notify = DirectNotifyGlobal.directNotify.newCategory('EstateWorldOperation')

    def __init__(self, manager, world):
        self.manager = manager
        self.air = manager.air
        self.world = world
        self.estateFields = {}
        self.houseFields = {}
        self.slots = []
        self.slot = 0

    def start(self):
        self.air.dbInterface.queryObject(self.air.dbId, self.world.estateId,
                                         self.__handleEstateRetrieved)

    def __handleEstateRetrieved(self, dclass, fields):
        if dclass != self.air.dclassesByName['DistributedEstateAI']:
            self.notify.warning('Could not read estate %s!' % self.world.estateId)
            self.__finish()
            return

        self.estateFields = fields
        self.slots = [slot for slot in range(NUM_HOUSE_SLOTS) if self.world.houseIds[slot]]
        self.__nextHouse()

    def __nextHouse(self):
        if not self.slots:
            self.__generate()
            return

        self.slot = self.slots.pop(0)
        self.air.dbInterface.queryObject(self.air.dbId, self.world.houseIds[self.slot],
                                         self.__handleHouseRetrieved)

    def __handleHouseRetrieved(self, dclass, fields):
        if dclass != self.air.dclassesByName['DistributedHouseAI']:
            self.notify.warning('Could not read house %s!' % self.world.houseIds[self.slot])
        else:
            self.houseFields[self.slot] = fields

        self.__nextHouse()

    def __generate(self):
        world = self.world
        world.zoneId = self.air.allocateZone(owner=world.ownerId)
        dropStaleObject(self.air, world.estateId)
        estate = DistributedEstateAI(self.air)
        estate.loadFromDb(self.estateFields)
        estate.dbObject = 1
        estate.generateWithRequiredAndId(world.estateId, self.air.districtId, world.zoneId)
        world.estate = estate
        for slot in sorted(self.houseFields):
            dropStaleObject(self.air, world.houseIds[slot])
            house = DistributedHouseAI(self.air)
            house.loadFromDb(self.houseFields[slot])
            house.setHousePos(slot)
            house.dbObject = 1
            house.generateWithRequiredAndId(world.houseIds[slot], self.air.districtId,
                                            world.zoneId)
            house.createInterior()
            house.d_setHouseReady()
            world.houses.append(house)

        self.__finish()

    def __finish(self):
        self.manager.worldReady(self.world)
