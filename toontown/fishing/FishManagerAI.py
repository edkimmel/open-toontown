import random

from direct.directnotify import DirectNotifyGlobal

from toontown.fishing import FishBase
from toontown.fishing import FishGlobals


class FishManagerAI:
    """The AI side of fishing: rolling a catch and selling a tank.

    `DistributedNPCFishermanAI.completeSale` and
    `DistributedNPCPetclerkAI.fishSold` both call `creditFishTank` and
    branch on its return value, so the sale is valued, paid and persisted
    entirely here.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('FishManagerAI')

    def __init__(self, air):
        self.air = air

    def creditFishTank(self, av):
        """Sell everything in av's tank.  Returns whether a new trophy was
        earned, which is the flag both sell movies branch on."""
        # the price is always recomputed from the toon's own tank; no
        # client ever supplies it
        value = av.fishTank.getTotalValue()
        av.addMoney(value)
        for fish in av.fishTank.getFish():
            av.fishCollection.collectFish(fish)

        av.b_setFishCollection(*av.fishCollection.getNetLists())
        av.b_setFishTank([], [], [])
        return self.checkTrophies(av)

    def checkTrophies(self, av):
        """One trophy per FISH_PER_BONUS species in the album, capped at the
        seven TrophyDict entries and never taken away again."""
        numTrophies = len(av.fishCollection) // FishGlobals.FISH_PER_BONUS
        numTrophies = min(numTrophies, len(FishGlobals.TrophyDict))
        if numTrophies <= len(av.getFishingTrophies()):
            return 0
        av.b_setFishingTrophies(list(range(numTrophies)))
        return 1

    def rollCatchType(self, rNumGen = None):
        if rNumGen is None:
            diceRoll = random.random()
        else:
            diceRoll = rNumGen.random()
        roll = min(int(diceRoll * 100) + 1, FishGlobals.SortedProbabilityCutoffs[-1])
        for cutoff in FishGlobals.SortedProbabilityCutoffs:
            if roll <= cutoff:
                return FishGlobals.ProbabilityDict[cutoff]

        return FishGlobals.BootItem

    def getCatch(self, av, pondArea, rNumGen = None):
        """Roll one catch for av in pondArea.  Returns the
        (code, itemDesc1, itemDesc2, itemDesc3) the spot's PullInMovie
        carries; `rNumGen` is threaded through so a caller can make the
        whole roll repeatable."""
        rodId = av.getFishingRod()
        catchType = self.rollCatchType(rNumGen)
        if catchType == FishGlobals.JellybeanItem:
            money = FishGlobals.Rod2JellybeanDict[rodId]
            av.addMoney(money)
            return (FishGlobals.JellybeanItem, money, 0, 0)
        if catchType != FishGlobals.FishItem:
            return (FishGlobals.BootItem, 0, 0, 0)
        success, genus, species, weight = FishGlobals.getRandomFishVitals(pondArea, rodId, rNumGen)
        if not success:
            self.notify.warning('no fish available in pond %s for rod %s' % (pondArea, rodId))
            return (FishGlobals.Nothing, 0, 0, 0)
        fish = FishBase.FishBase(genus, species, weight)
        # the album is only read here; it is written when the tank is sold
        collectResult = av.fishCollection.getCollectResult(fish)
        if not av.addFishToTank(fish):
            return (FishGlobals.OverTankLimit, 0, 0, 0)
        if collectResult == FishGlobals.COLLECT_NEW_ENTRY:
            code = FishGlobals.FishItemNewEntry
        elif collectResult == FishGlobals.COLLECT_NEW_RECORD:
            code = FishGlobals.FishItemNewRecord
        else:
            code = FishGlobals.FishItem
        return (code, genus, species, weight)
