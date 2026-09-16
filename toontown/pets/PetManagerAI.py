from direct.directnotify import DirectNotifyGlobal
import random

class PetManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('PetManagerAI')

    def __init__(self, air):
        self.air = air
        self.randomGenerator = random.Random()

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
