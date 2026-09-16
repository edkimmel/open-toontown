from direct.directnotify import DirectNotifyGlobal

from toontown.estate.EstateProvisioner import NUM_HOUSE_SLOTS

# The flower-sell wheelbarrow's own position (DistributedEstate.py:399), the
# anchor the fireworks cannon is offset from.  No reference placement exists
# for this prop -- the offset itself is invented, just far enough from the
# wheelbarrow that the two props' collision spheres do not overlap.
WHEELBARROW_POS = (-142.586, 4.353, 0.025)
FIREWORKS_CANNON_OFFSET = (10.0, 0.0, 0.0)

# The estate's four fishing_spot props, (x, y, z, h, p, r), lifted from
# resources/phase_5.5/dna/estate_1.dna:6-25 -- the "fishing_pond_1" group's
# four "fishing_spot_DNARoot" props, in file order. The AI never parses the
# estate's DNA (dnaDataMap is built for hood zones only,
# ToontownAIRepository.py:258-263), so these are module constants, the same
# WHEELBARROW_POS pattern above.
FISHING_SPOT_POSES = (
    (49.1029, -124.805, 0.344704, 90, 0, 0),
    (46.5222, -134.739, 0.390713, 75, 0, 0),
    (41.31, -144.559, 0.375978, 45, 0, 0),
    (46.8254, -113.682, 0.46015, 135, 0, 0),
)

# Where a pet is put when it is activated into an estate.
# DistributedPetAI.generate drops a freshly activated pet at a random point
# in a +/-20 box around the zone origin with no ground check (:512-514),
# which in the estate is the pond, a house, or off the terrain.  This is the
# flower-sell wheelbarrow's own patch of lawn (WHEELBARROW_POS above,
# DistributedEstate.py:399) with the same ground z, 12 units along +y so the
# pet stands clear of the wheelbarrow and of the fireworks cannon 10 units
# along +x; it is ~224 units from the fishing pond's circle
# (FishingTargetGlobals centre (30, -126, -0.3), radius 16).
PET_POS = (-142.586, 16.353, 0.025)


def makeFireworksCannon(air, world):
    """Generate the estate's one fireworks cannon into its zone, at a fixed
    offset from the flower-sell wheelbarrow.  Permanent and always
    generated (no rental gate, unlike the pinball cannon) -- shared by
    EstateWorldOperation.__populate and the ~fireworkscannon magic word so
    there is exactly one placement policy."""
    from toontown.estate.DistributedFireworksCannonAI import DistributedFireworksCannonAI

    x = WHEELBARROW_POS[0] + FIREWORKS_CANNON_OFFSET[0]
    y = WHEELBARROW_POS[1] + FIREWORKS_CANNON_OFFSET[1]
    z = WHEELBARROW_POS[2] + FIREWORKS_CANNON_OFFSET[2]
    cannon = DistributedFireworksCannonAI(air, getattr(air, 'fireworkMgr', None), x, y, z)
    cannon.generateWithRequired(world.zoneId)
    return cannon


def makeFishingPond(air, world):
    """Generate the estate's one fishing pond, its four spots and its
    targets into the estate zone -- permanent and always generated, the
    fireworks-cannon pattern above. The pond's area is
    ToontownGlobals.MyEstate, the key into FishingTargetGlobals and
    FishGlobals.__pondInfoDict, not the allocated zone the pond, its spots
    and its targets are actually generated into (open question (g))."""
    from toontown.ai.ToontownAIRepository import makeFishingTargets
    from toontown.fishing.DistributedFishingPondAI import DistributedFishingPondAI
    from toontown.safezone.DistributedFishingSpotAI import DistributedFishingSpotAI
    from toontown.toonbase import ToontownGlobals

    pond = DistributedFishingPondAI(air)
    pond.setArea(ToontownGlobals.MyEstate)
    pond.generateWithRequired(world.zoneId)

    spots = []
    for x, y, z, h, p, r in FISHING_SPOT_POSES:
        spot = DistributedFishingSpotAI(air, pond.doId, x, y, z, h, p, r)
        spot.generateWithRequired(world.zoneId)
        spots.append(spot)

    world.fishingPond = pond
    world.fishingSpots = spots
    world.fishingTargets = makeFishingTargets(air, pond)
    return pond


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


def teardownFishingPond(world):
    """Remove the estate's fishing pond, its spots and its targets, spots
    and targets first so the pond is the last of the three to go -- shared
    by EstateWorld.destroy and the ~pond magic word so there is exactly one
    teardown order."""
    for spot in world.fishingSpots:
        spot.requestDelete()
    world.fishingSpots = []

    for target in world.fishingTargets:
        target.requestDelete()
    world.fishingTargets = []

    if world.fishingPond is not None:
        world.fishingPond.requestDelete()
        world.fishingPond = None


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
        self.fireworksCannon = None
        self.fishingPond = None
        self.fishingSpots = []
        self.fishingTargets = []
        self.pets = []

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
        if self.fireworksCannon is not None:
            self.fireworksCannon.requestDelete()
            self.fireworksCannon = None

        teardownFishingPond(self)

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
        from toontown.toonbase import ToontownGlobals

        world = self.world
        world.estate = self.air.doId2do[world.estateId]
        # cannonEnabled has no db field of its own (etc/toon.dc:1219 is
        # `required` only), so a re-activated world has to re-derive it from
        # the estate's own db-backed rental fields -- a rental already
        # expired by the time announceGenerate's own catch-up ran, so a
        # rentalType still showing RentalCannon here means the rental is
        # live and the pair regenerates; anything else means no cannon.
        liveCannonRental = world.estate.getRentalType() == ToontownGlobals.RentalCannon
        for slot in sorted(self.houseFields):
            house = self.air.doId2do[world.houseIds[slot]]
            house.setHousePos(slot)
            house.createInterior()
            house.createMailbox()
            house.createGarden(world.estate)
            if liveCannonRental:
                house.setCannonEnabled(1)
            house.createCannon(world.estate)
            world.houses.append(house)

        # The fireworks cannon is a permanent, always-generated estate prop
        # (unlike the rental-gated pinball cannon above) -- one per estate,
        # regardless of how many house slots are occupied.
        if world.fireworksCannon is None:
            world.fireworksCannon = makeFireworksCannon(self.air, world)

        # The fishing pond is the same shape -- one per estate, permanent,
        # independent of house-slot occupancy.
        if world.fishingPond is None:
            makeFishingPond(self.air, world)

        self.__activatePets()

    def __activatePets(self):
        """Bring the pet of every toon this estate is being opened for into
        the estate zone.  A pet is a database object of its own, so it is
        activated, not generated -- the same rule, and the same wait, the
        estate and the houses use at :211-241 above."""
        world = self.world
        avIds = [world.ownerId]
        avIds.extend(avId for avId in world.occupants if avId not in avIds)
        self.activating = []
        for avId in avIds:
            av = self.air.doId2do.get(avId)
            petId = getattr(av, 'petId', 0)
            if petId and petId not in self.activating:
                self.activating.append(petId)

        if not self.activating:
            self.__finish()
            return

        for doId in self.activating:
            self.air.sendActivate(doId, self.air.districtId, world.zoneId)

        self.waited = 0
        self.__waitForPets()

    def __waitForPets(self, task=None):
        missing = [doId for doId in self.activating if doId not in self.air.doId2do]
        if missing:
            self.waited += 1
            if self.waited > self.ACTIVATE_TRIES:
                # unlike the estate and the houses, a pet that never comes
                # back is not worth holding the estate closed for
                self.notify.warning('Pets %s never activated!' % missing)
            else:
                taskMgr.doMethodLater(self.ACTIVATE_POLL, self.__waitForPets,
                                      'estate-pet-activate-%s' % self.world.estateId)
                return

        self.__placePets()

    def __placePets(self):
        world = self.world
        for doId in self.activating:
            pet = self.air.doId2do.get(doId)
            if pet is None:
                continue

            world.pets.append(placePet(pet))

        self.activating = []
        self.__finish()

    def __finish(self):
        self.manager.worldReady(self.world)
