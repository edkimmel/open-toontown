from direct.directnotify import DirectNotifyGlobal
from toontown.pets import PetDNA, PetMood, PetTraits, PetUtil
from toontown.pets.PetNameGenerator import PetNameGenerator
import random
import time

# The nine DNA slots in the order getRandomPetDNA returns them
# (PetDNA.py:182-207), paired with the db fields they fill
# (etc/toon.dc:2420-2428).
PetDNAFields = ('setHead',
 'setEars',
 'setNose',
 'setTail',
 'setBodyTexture',
 'setColor',
 'setColorScale',
 'setEyeColor',
 'setGender')

class PetManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('PetManagerAI')

    def __init__(self, air):
        self.air = air
        self.randomGenerator = random.Random()
        self.nameGenerator = None

    def getAvailablePets(self, numResults, numReserved=0):
        # Draw numResults fresh pet seeds. A seed is a uint32
        # (etc/toon.dc setPetSeeds) that, together with a safezone id,
        # resolves through PetUtil.getPetInfoFromSeed to a complete pet --
        # name, DNA and traitSeed -- with no further server traffic
        # (PetUtil.py:6-14). The list only needs to be internally
        # consistent for the life of the caller's session (the clerk
        # stores it as self.petSeeds and re-prices from it at
        # petAdopted), so a fresh draw per call already satisfies that.
        #
        # This uses its own random.Random rather than the module-level
        # random, because PetUtil.getPetInfoFromSeed saves and restores
        # the global RNG state around its own draw (PetUtil.py:7,12); if
        # this manager drew from the same generator, that save/restore
        # would make the two draws depend on each other's call order.
        #
        # numReserved is the two call sites' second argument --
        # DistributedNPCPetclerkAI.py:29 passes 2 (len(PetDNA.PetGenders),
        # which it then multiplies the returned list by) and
        # PetshopBuildingAI.py:33 passes len(self.npcs) and discards the
        # result entirely. Neither caller reserves anything today, so this
        # is read as "how many NPC-owned pets to reserve alongside the
        # player-facing ones" and ignored: the return is always exactly
        # numResults seeds.
        return [self.randomGenerator.getrandbits(32) for i in range(numResults)]

    def getPetName(self, nameIndex):
        # The name the player picked in the shop's name list, resolved
        # through the same table PetNameGenerator draws its random names
        # from (PetNameGenerator.py:52-56; the clerk has already bounded
        # the index by TTLocalizer.PetNameIndexMAX,
        # DistributedNPCPetclerkAI.py:107-110). Returns None when the
        # table cannot be read at all, so the caller can fall back to the
        # seed's own name rather than leave the pet unnamed.
        if self.nameGenerator is None:
            try:
                self.nameGenerator = PetNameGenerator()
            except Exception:
                self.notify.warning('could not read the pet name list')
                return None
        return self.nameGenerator.getName(nameIndex)

    def createNewPetFromSeed(self, ownerId, seed, nameIndex=None, gender=None,
                             safeZoneId=None, callback=None):
        # Create the database row for a freshly adopted pet and link it to
        # its owner. The caller is the pet clerk
        # (DistributedNPCPetclerkAI.py:111), which has already validated
        # petNum, the price and nameIndex, and which charges the toon
        # right after this returns (:113-116).
        #
        # The seed is the whole pet: getPetInfoFromSeed draws the DNA, a
        # name and a traitSeed from it and restores the global RNG state
        # it borrowed (PetUtil.py:6-14). Two things then override what the
        # seed said: the clerk's gender, because the shop shows each seed
        # once per gender and the list index carries the choice
        # (DistributedNPCPetclerkAI.py:30-31,106), and the player's name
        # pick, because the shop's name list is what they were shown.
        name, dnaArray, traitSeed = PetUtil.getPetInfoFromSeed(seed, safeZoneId)
        if gender is not None:
            PetDNA.setGender(dnaArray, gender)
        if nameIndex is not None:
            pickedName = self.getPetName(nameIndex)
            if pickedName:
                name = pickedName
        # Traits are written resolved rather than as zeros. DistributedPetAI
        # backfills any trait still 0.0 from the traitSeed when the pet is
        # first activated (:491-501), so zeros would also work -- but the
        # price the clerk charged was computed from these exact values
        # (PetUtil.getPetCostFromSeed:17-29), and a row that already carries
        # them is what the pet was sold as, with nothing left to resolve.
        traits = PetTraits.PetTraits(traitSeed, safeZoneId)
        fields = {'DcObjectType': 'DistributedPet',
                  'setOwnerId': (ownerId,),
                  'setPetName': (name,),
                  'setTraitSeed': (traitSeed,),
                  'setSafeZone': (safeZoneId,),
                  'setLastSeenTimestamp': (int(time.time()),),
                  'setTrickAptitudes': ([],)}
        # PetTraits.TraitDescs (:143-157) is in the same order as the 13
        # trait fields of etc/toon.dc:2407-2419, and each field is named
        # for its trait.
        for traitName in PetTraits.getTraitNames():
            fieldName = 'set%s%s' % (traitName[0].upper(), traitName[1:])
            fields[fieldName] = (traits.getTraitValue(traitName),)
        for i, fieldName in enumerate(PetDNAFields):
            fields[fieldName] = (dnaArray[i],)
        # A new pet starts with every mood component at zero; PetMood
        # drifts them from there once the pet is activated
        # (PetMood.py:10, DistributedPetAI.py:517-520).
        for component in PetMood.PetMood.Components:
            fields['set%s%s' % (component[0].upper(), component[1:])] = (0.0,)
        self.air.dbInterface.createObject(self.air.dbId,
                                          self.air.dclassesByName['DistributedPetAI'],
                                          fields,
                                          lambda petId: self.__handlePetCreated(petId, ownerId, callback))

    def __handlePetCreated(self, petId, ownerId, callback=None):
        # The EstateProvisioner.__handleHouseCreated shape (:171-189): a
        # falsy doId is a failed create, and the owner is linked in memory
        # when it is online and on its database row when it is not. The
        # pet is deliberately not generated here -- it comes into the
        # world with its owner's estate, not with the adoption.
        if not petId:
            self.notify.warning('failed to create a pet for avatar %s!' % ownerId)
            if callback is not None:
                callback(0)
            return
        av = self.air.doId2do.get(ownerId)
        if av is not None:
            av.b_setPetId(petId)
        else:
            self.air.dbInterface.updateObject(self.air.dbId, ownerId,
                                              self.air.dclassesByName['DistributedToonAI'],
                                              {'setPetId': (petId,)})
        if callback is not None:
            callback(petId)
