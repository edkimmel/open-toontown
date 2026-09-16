from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI
from toontown.estate import GardenGlobals
from toontown.estate.DistributedFlowerAI import DistributedFlowerAI
from toontown.estate.DistributedGagTreeAI import DistributedGagTreeAI
from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI
from toontown.estate.DistributedToonStatuaryAI import DistributedToonStatuaryAI


class DistributedGardenPlotAI(DistributedLawnDecorAI):
    """An empty garden hard point (etc/toon.dc:2687).  `setPlot` is the hard
    point index into `GardenGlobals.estatePlots[ownerIndex]`, the same pair
    `whatCanBePlanted(ownerIndex, plot)` (GardenGlobals.py:1277) reads to
    decide what may grow here -- `ownerIndex` doubles as the owning house's
    `gardenPos` (DistributedHouseAI.createGarden).

    `plantFlower`/`plantGagTree`/`plantStatuary`/`plantToonStatuary`/
    `plantNothing` (etc/toon.dc:2688-2692) are only honored for the owner,
    and only inside the one-avatar session `plotEntered` grants (`self.busy`,
    landed in B2) -- the client's own gate
    (`DistributedGardenPlot.py:109-113`'s `canBePlanted`) is a UI convenience,
    not a security boundary, the same reasoning `test_lawn_decor_ai.py`
    already applies to `plotEntered`/`removeItem`.  A successful plant
    replaces this plot DO with the grown-object DO
    (`DistributedFlowerAI`/`DistributedGagTreeAI`/`DistributedStatuaryAI`/
    `DistributedToonStatuaryAI`) at the same zone/position/heading/
    ownerIndex, and writes a `lawnItem` (etc/toon.dc:1161 --
    type/hardPoint/waterLevel/growthLevel/optional) into the owner's
    `estateAI.slotNItems` list (`DistributedEstateAI.b_setSlotItems`) --
    there is no separate persistence path.
    """

    def _sessionToon(self):
        """The sending avatar and its `DistributedToonAI`, or `(0, None)` if
        the sender is not the owner mid-`plotEntered` session."""
        avId = self.air.getAvatarIdFromSender()
        if avId != self.getOwnerAvId() or self.busy != avId:
            return (0, None)
        return (avId, self.air.doId2do.get(avId))

    def _endSession(self, avId):
        # Mirrors DistributedLawnDecorAI's private __release, minus the
        # setMovie broadcast -- the plot is about to be deleted (or, for
        # plantNothing, simply reusable), not handed a movie mode.
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.busy = 0

    def _writeLawnItem(self, plantType, waterLevel, growthLevel, optional):
        items = list(self.estateAI.slotItems[self.ownerIndex])
        items.append((plantType, self.plot, waterLevel, growthLevel, optional))
        self.estateAI.b_setSlotItems(self.ownerIndex, items)

    def _replaceWithGrownObject(self, growCls, typeIndex, waterLevel, growthLevel,
                                optional, extraSetters=()):
        grown = growCls(self.air, self.estateAI)
        grown.setPlot(self.plot)
        grown.setPosition(*self.position)
        grown.setHeading(self.heading)
        grown.setOwnerIndex(self.ownerIndex)
        grown.setTypeIndex(typeIndex)
        grown.setWaterLevel(waterLevel)
        grown.setGrowthLevel(growthLevel)
        for setterName, value in extraSetters:
            getattr(grown, setterName)(value)
        grown.generateWithRequired(self.zoneId)
        self._writeLawnItem(typeIndex, waterLevel, growthLevel, optional)
        self.requestDelete()

    def _specialIndexForSpecies(self, species):
        # A statuary's `gardenSpecial` index lives one hop away from its
        # species: PlantAttributes[species]['varieties'] is always a single
        # (recipeKey, ...) tuple for statuary (e.g. species 200 ->
        # recipeKey 1000), and Recipes[recipeKey]['special'] is the actual
        # gardenSpecial index (100) the toon's setGardenSpecials list carries
        # -- GardenGlobals.py:212-216,428-429.
        attrib = GardenGlobals.PlantAttributes.get(species)
        varieties = attrib.get('varieties') if attrib else None
        if not varieties:
            return -1
        recipe = GardenGlobals.Recipes.get(varieties[0][0])
        if not recipe:
            return -1
        return recipe.get('special', -1)

    def _consumeGardenSpecial(self, toon, species):
        index = self._specialIndexForSpecies(species)
        if index < 0:
            return False
        for specialIndex, count in toon.getGardenSpecials():
            if specialIndex == index and count > 0:
                toon.removeGardenItem(index, 1)
                return True
        return False

    def plantFlower(self, species, variety):
        avId, toon = self._sessionToon()
        if not avId or toon is None:
            return
        if GardenGlobals.whatCanBePlanted(self.ownerIndex, self.plot) != GardenGlobals.FLOWER_TYPE:
            return
        attrib = GardenGlobals.PlantAttributes.get(species)
        if not attrib or attrib.get('plantType') != GardenGlobals.FLOWER_TYPE:
            return
        varieties = attrib.get('varieties', ())
        if variety < 0 or variety >= len(varieties):
            return
        numBeans = GardenGlobals.getNumBeansRequired(species, variety)
        if numBeans < 0 or not toon.takeMoney(numBeans):
            return
        self._endSession(avId)
        # lawnItem has no separate variety slot -- it rides in `optional`,
        # the same way DistributedFlower's own setVariety is a bolt-on next
        # to DistributedPlantBase's setTypeIndex (etc/toon.dc:2724-2727).
        self._replaceWithGrownObject(DistributedFlowerAI, species, 0, 0, variety,
                                     extraSetters=[('setVariety', variety)])

    def plantGagTree(self, track, level):
        avId, toon = self._sessionToon()
        if not avId or toon is None:
            return
        if GardenGlobals.whatCanBePlanted(self.ownerIndex, self.plot) != GardenGlobals.GAG_TREE_TYPE:
            return
        inventory = getattr(toon, 'inventory', None)
        if inventory is None or inventory.numItem(track, level) <= 0:
            return
        # Planting a gag tree spends one of that gag from the toon's own
        # inventory (PlantTreeGUI.py:32-37's own gate before it ever sends
        # this update), not jellybeans.
        inventory.useItem(track, level)
        toon.b_setInventory(inventory.makeNetString())
        self._endSession(avId)
        typeIndex = GardenGlobals.getTreeTypeIndex(track, level)
        self._replaceWithGrownObject(DistributedGagTreeAI, typeIndex, 0, 0, 0)

    def plantStatuary(self, species):
        avId, toon = self._sessionToon()
        if not avId or toon is None:
            return
        if GardenGlobals.whatCanBePlanted(self.ownerIndex, self.plot) != GardenGlobals.STATUARY_TYPE:
            return
        attrib = GardenGlobals.PlantAttributes.get(species)
        if not attrib or attrib.get('plantType') != GardenGlobals.STATUARY_TYPE:
            return
        if species in GardenGlobals.ToonStatuaryTypeIndices:
            # that is plantToonStatuary's species range
            return
        if not self._consumeGardenSpecial(toon, species):
            return
        self._endSession(avId)
        self._replaceWithGrownObject(DistributedStatuaryAI, species, 0, 0, 0)

    def plantToonStatuary(self, species, dnaCode):
        avId, toon = self._sessionToon()
        if not avId or toon is None:
            return
        if GardenGlobals.whatCanBePlanted(self.ownerIndex, self.plot) != GardenGlobals.STATUARY_TYPE:
            return
        if species not in GardenGlobals.ToonStatuaryTypeIndices:
            return
        if not self._consumeGardenSpecial(toon, species):
            return
        self._endSession(avId)
        self._replaceWithGrownObject(DistributedToonStatuaryAI, species, 0, 0, dnaCode,
                                     extraSetters=[('setOptional', dnaCode)])

    def plantNothing(self, burntBeans):
        avId, toon = self._sessionToon()
        if not avId or toon is None:
            return
        if burntBeans > 0:
            toon.takeMoney(burntBeans)
        self._endSession(avId)
