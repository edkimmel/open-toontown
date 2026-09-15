from direct.directnotify import DirectNotifyGlobal

from toontown.estate.EstateProvisioner import NUM_HOUSE_SLOTS


class EstateWorld:
    """One account's estate while it is live: the zone it was generated in,
    the objects activated there, and the avatars standing in it.  The estate
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


class EstateWorldOperation:
    """Reads the persisted estate and house records, then activates them into
    a freshly allocated zone."""

    notify = DirectNotifyGlobal.directNotify.newCategory('EstateWorldOperation')

    # how long to wait for the activated objects to come back from the DBSS
    ACTIVATE_POLL = 0.2
    ACTIVATE_TRIES = 50

    def __init__(self, manager, world):
        self.manager = manager
        self.air = manager.air
        self.world = world
        self.estateFields = {}
        self.houseFields = {}
        self.slots = []
        self.slot = 0
        self.activating = []
        self.waited = 0

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
        # The estate and the houses are database objects, and a database
        # object is brought into the world by activating it on the DBSS --
        # the way a toon is loaded (otp/login/AstronLoginManagerUD.py:779,
        # direct/distributed/AstronInternalRepository.py's sendActivate).
        # generateWithRequiredAndId would ask the State Server for a second
        # object on a doId the DBSS already owns; the AI gets its object
        # either way, but nothing in the zone is ever sent to a client.
        self.activating = [world.estateId]
        self.activating.extend(world.houseIds[slot] for slot in sorted(self.houseFields))
        for doId in self.activating:
            self.air.sendActivate(doId, self.air.districtId, world.zoneId)

        self.__waitForActivation()

    def __waitForActivation(self, task=None):
        # The activated objects arrive as ENTER_AI entries, which is the only
        # thing that puts them in air.doId2do
        # (direct/distributed/AstronInternalRepository.py:272-300).
        missing = [doId for doId in self.activating if doId not in self.air.doId2do]
        if missing:
            self.waited += 1
            if self.waited > self.ACTIVATE_TRIES:
                self.notify.warning('Estate objects %s never activated!' % missing)
                self.__finish()
                return

            taskMgr.doMethodLater(self.ACTIVATE_POLL, self.__waitForActivation,
                                  'estate-activate-%s' % self.world.estateId)
            return

        self.__populate()

    def __populate(self):
        world = self.world
        world.estate = self.air.doId2do[world.estateId]
        for slot in sorted(self.houseFields):
            house = self.air.doId2do[world.houseIds[slot]]
            house.setHousePos(slot)
            house.createInterior()
            house.d_setHouseReady()
            world.houses.append(house)

        self.__finish()

    def __finish(self):
        self.manager.worldReady(self.world)
