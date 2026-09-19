from direct.directnotify import DirectNotifyGlobal

from toontown.estate.EstateProvisioner import NUM_HOUSE_SLOTS

# Where a pet is put when it is activated into an estate.
# DistributedPetAI.generate drops a freshly activated pet at a random point
# in a +/-20 box around the zone origin with no ground check (:512-514),
# which in the estate is the pond, a house, or off the terrain.  This is the
# flower-sell wheelbarrow's own patch of lawn (DistributedEstate.py:399)
# with the same ground z, 12 units along +y so the
# pet stands clear of the wheelbarrow and of the fireworks cannon 10 units
# along +x; it is ~224 units from the fishing pond's circle
# (FishingTargetGlobals centre (30, -126, -0.3), radius 16).
PET_POS = (-142.586, 16.353, 0.025)


def placePet(pet):
    """Put an activated pet on the estate's lawn, overriding the random
    position generate() gave it."""
    pet.setPos(*PET_POS)
    pet.setH(0)
    return pet


def teardownPets(world):
    """Drop the estate's pets.  requestDelete, never delete: it stamps the
    pet's last-seen timestamp and unwinds the simulation
    (DistributedPetAI.py:544-553,569-624), and the record stays so the next
    visit activates the same doId again."""
    for pet in world.pets:
        pet.requestDelete()

    world.pets = []


class EstatePetActivation:
    """Activate one or more persistent pets into a live estate.

    Estate opening and a later visitor admission use the same DBSS lifecycle:
    the persistent pet must arrive as an ENTER_AI object before it can be
    placed on the lawn.  ``world.activatingPetIds`` makes concurrent/repeated
    admissions harmless while the DBSS response is still in flight.
    """

    ACTIVATE_POLL = 0.2
    ACTIVATE_TRIES = 50
    notify = DirectNotifyGlobal.directNotify.newCategory('EstatePetActivation')

    def __init__(self, air, world, avIds, callback=None):
        self.air = air
        self.world = world
        self.avIds = list(avIds)
        self.callback = callback
        self.activating = []
        self.waited = 0

    def start(self):
        placed = set(pet.doId for pet in self.world.pets)
        for avId in self.avIds:
            av = self.air.doId2do.get(avId)
            petId = getattr(av, 'petId', 0)
            if (petId and petId not in placed and
                    petId not in self.world.activatingPetIds and
                    petId not in self.activating):
                self.activating.append(petId)

        if not self.activating:
            self.__finish()
            return

        self.world.activatingPetIds.update(self.activating)
        for doId in self.activating:
            self.air.sendActivate(doId, self.air.districtId, self.world.zoneId)

        self.__waitForPets()

    def __waitForPets(self, task=None):
        missing = [doId for doId in self.activating if doId not in self.air.doId2do]
        if missing:
            self.waited += 1
            if self.waited > self.ACTIVATE_TRIES:
                self.notify.warning('Pets %s never activated!' % missing)
            else:
                taskMgr.doMethodLater(self.ACTIVATE_POLL, self.__waitForPets,
                                      'estate-pet-activate-%s-%s' %
                                      (self.world.estateId, '-'.join(str(doId)
                                                                       for doId in self.activating)))
                return

        placed = set(pet.doId for pet in self.world.pets)
        for doId in self.activating:
            self.world.activatingPetIds.discard(doId)
            pet = self.air.doId2do.get(doId)
            if pet is not None and doId not in placed:
                self.world.pets.append(placePet(pet))
                placed.add(doId)

        self.__finish()

    def __finish(self):
        if self.callback is not None:
            self.callback()


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
        self.pets = []
        # Pet DBSS activations can overlap when an already-open estate admits
        # a second toon.  Keep their persistent ids separate from ``pets``:
        # an object only joins ``pets`` after its ENTER_AI arrives and it has
        # been placed on the lawn.
        self.activatingPetIds = set()

    def addOccupant(self, avId):
        if avId not in self.occupants:
            self.occupants.append(avId)

    def removeOccupant(self, avId):
        if avId in self.occupants:
            self.occupants.remove(avId)

    def getHouseZones(self):
        return [house.interiorZoneId for house in self.houses
                if house.interiorZoneId is not None]

    def destroy(self, air):
        """Unload the world.  The houses take their own children with them
        (DistributedHouseAI.destroy); the estate and the houses themselves are
        database objects, so their delete is an unload and the next visit
        activates the same doIds again."""
        # the pets first: a pet unwinds its own simulation as it goes, and
        # announceZoneChange reads the estate it is standing in
        # (DistributedPetAI.py:135-142)
        teardownPets(self)

        for house in self.houses:
            house.destroy()

        self.houses = []
        if self.estate is not None:
            self.estate.requestDelete()
            self.estate = None

        if self.zoneId is not None:
            air.deallocateZone(self.zoneId)
            self.zoneId = None

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

        self.__activatePets()

    def __activatePets(self):
        """Bring the pet of every toon this estate is being opened for into
        the estate zone.  A pet is a database object of its own, so it is
        activated, not generated -- the same rule, and the same wait, the
        estate and the houses use at :211-241 above."""
        world = self.world
        avIds = [world.ownerId]
        avIds.extend(avId for avId in world.occupants if avId not in avIds)
        EstatePetActivation(self.air, world, avIds, self.__finish).start()

    def __finish(self):
        self.manager.worldReady(self.world)
