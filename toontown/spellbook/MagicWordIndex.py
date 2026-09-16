##################################################
# The Toontown Offline Magic Word Manager
##################################################
# Author: Benjamin Frisby
# Copyright: Copyright 2020, Toontown Offline
# Credits: Benjamin Frisby, John Cote, Ruby Lord, Frank, Nick, Little Cat, Ooowoo
# License: MIT
# Version: 1.0.0
# Email: belloqzafarian@gmail.com
##################################################

import collections, types

from direct.distributed.ClockDelta import *
from direct.interval.IntervalGlobal import *
from direct.showbase.DirectObject import DirectObject
from direct.showbase.PythonUtil import *

from panda3d.otp import NametagGroup, WhisperPopup

from otp.otpbase import OTPLocalizer
from otp.otpbase import OTPGlobals
from otp.otpbase.PythonUtil import *

from . import MagicWordConfig
import time, random, re, json

magicWordIndex = collections.OrderedDict()


class MagicWord(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('MagicWord')

    # Whether this Magic word should be considered "hidden"
    # If your Toontown source has a page for Magic Words in the Sthickerbook, this will be useful for that
    hidden = False

    # Whether this Magic Word is an administrative command or not
    # Good for config settings where you want to disable cheaty Magic Words, but still want moderation ones
    administrative = False

    # List of names that will also invoke this word - a setHP magic word might have "hp", for example
    # A Magic Word will always be callable with its class name, so you don't have to put that in the aliases
    aliases = None

    # Description of the Magic Word
    # If your Toontown source has a page for Magic Words in the Sthickerbook, this will be useful for that
    desc = MagicWordConfig.MAGIC_WORD_DEFAULT_DESC

    # Advanced description that gives the user a lot more information than normal
    # If your Toontown source has a page for Magic Words in the Sthickerbook, this will be useful for that
    advancedDesc = MagicWordConfig.MAGIC_WORD_DEFAULT_ADV_DESC

    # Default example with for commands with no arguments set
    # If your Toontown source has a page for Magic Words in the Sthickerbook, this will be useful for that
    example = ""

    # The minimum access level required to use this Magic Word
    accessLevel = 'MODERATOR'

    # A restriction on the Magic Word which sets what kind or set of Distributed Objects it can be used on
    # By default, a Magic Word can affect everyone
    affectRange = [MagicWordConfig.AFFECT_SELF, MagicWordConfig.AFFECT_OTHER, MagicWordConfig.AFFECT_BOTH]

    # Where the magic word will be executed -- EXEC_LOC_CLIENT or EXEC_LOC_SERVER
    execLocation = MagicWordConfig.EXEC_LOC_INVALID

    # List of all arguments for this word, with the format [(type, isRequired), (type, isRequired)...]
    # If the parameter is not required, you must provide a default argument: (type, False, default)
    arguments = None

    def __init__(self):
        if self.__class__.__name__ != "MagicWord":
            self.aliases = self.aliases if self.aliases is not None else []
            self.aliases.insert(0, self.__class__.__name__)
            self.aliases = [x.lower() for x in self.aliases]
            self.arguments = self.arguments if self.arguments is not None else []

            if len(self.arguments) > 0:
                for arg in self.arguments:
                    argInfo = ""
                    if not arg[MagicWordConfig.ARGUMENT_REQUIRED]:
                        argInfo += "(default: {0})".format(arg[MagicWordConfig.ARGUMENT_DEFAULT])
                    self.example += "[{0}{1}] ".format(arg[MagicWordConfig.ARGUMENT_NAME], argInfo)

            self.__register()

    def __register(self):
        for wordName in self.aliases:
            if wordName in magicWordIndex:
                self.notify.error('Duplicate Magic Word name or alias detected! Invalid name: {}'. format(wordName))
            magicWordIndex[wordName] = {'class': self,
                                        'classname': self.__class__.__name__,
                                        'hidden': self.hidden,
                                        'administrative': self.administrative,
                                        'aliases': self.aliases,
                                        'desc': self.desc,
                                        'advancedDesc': self.advancedDesc,
                                        'example': self.example,
                                        'execLocation': self.execLocation,
                                        'access': self.accessLevel,
                                        'affectRange': self.affectRange,
                                        'args': self.arguments}

    def loadWord(self, air=None, cr=None, invokerId=None, targets=None, args=None):
        self.air = air
        self.cr = cr
        self.invokerId = invokerId
        self.targets = targets
        self.args = args

    def executeWord(self):
        executedWord = None
        validTargets = len(self.targets)
        for avId in self.targets:
            invoker = None
            toon = None
            if self.air:
                invoker = self.air.doId2do.get(self.invokerId)
                toon = self.air.doId2do.get(avId)
            elif self.cr:
                invoker = self.cr.doId2do.get(self.invokerId)
                toon = self.cr.doId2do.get(avId)
            if hasattr(toon, "getName"):
                name = toon.getName()
            else:
                name = avId

            if not self.validateTarget(toon):
                if len(self.targets) > 1:
                    validTargets -= 1
                    continue
                return "{} is not a valid target!".format(name)

            # TODO: Should we implement locking?
            # if toon.getLocked() and not self.administrative:
            #     if len(self.targets) > 1:
            #         validTargets -= 1
            #         continue
            #     return "{} is currently locked. You can only use administrative commands on them.".format(name)

            if invoker.getAccessLevel() <= toon.getAccessLevel() and toon != invoker:
                if len(self.targets) > 1:
                    validTargets -= 1
                    continue
                targetAccess = OTPGlobals.AccessLevelDebug2Name.get(OTPGlobals.AccessLevelInt2Name.get(toon.getAccessLevel()))
                invokerAccess = OTPGlobals.AccessLevelDebug2Name.get(OTPGlobals.AccessLevelInt2Name.get(invoker.getAccessLevel()))
                return "You don't have a high enough Access Level to target {0}! Their Access Level: {1}. Your Access Level: {2}.".format(name, targetAccess, invokerAccess)

            if self.execLocation == MagicWordConfig.EXEC_LOC_CLIENT:
                self.args = json.loads(self.args)

            executedWord = self.handleWord(invoker, avId, toon, *self.args)
        # If you're only using the Magic Word on one person and there is a response, return that response
        if executedWord and len(self.targets) == 1:
            return executedWord
        # If the amount of targets is higher than one...
        elif validTargets > 0:
            # And it's only 1, and that's yourself, return None
            if validTargets == 1 and self.invokerId in self.targets:
                return None
            # Otherwise, state how many targets you executed it on
            return "Magic Word successfully executed on %s target(s)." % validTargets
        else:
            return "Magic Word unable to execute on any targets."

    def validateTarget(self, target):
        if self.air:
            from toontown.toon.DistributedToonAI import DistributedToonAI
            return isinstance(target, DistributedToonAI)
        elif self.cr:
            from toontown.toon.DistributedToon import DistributedToon
            return isinstance(target, DistributedToon)
        return False

    def handleWord(self, invoker, avId, toon, *args):
        raise NotImplementedError

class SetHP(MagicWord):
    aliases = ["hp", "setlaff", "laff"]
    desc = "Sets the target's current laff."
    advancedDesc = "This Magic Word will change the current amount of laff points the target has to whichever " \
                   "value you specify. You are only allowed to specify a value between -1 and the target's maximum " \
                   "laff points. If you specify a value less than 1, the target will instantly go sad unless they " \
                   "are in Immortal Mode."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("hp", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        hp = args[0]

        if not -1 <= hp <= toon.getMaxHp():
            return "Can't set {0}'s laff to {1}! Specify a value between -1 and {0}'s max laff ({2}).".format(
                toon.getName(), hp, toon.getMaxHp())

        if hp <= 0 and toon.immortalMode:
            return "Can't set {0}'s laff to {1} because they are in Immortal Mode!".format(toon.getName(), hp)

        toon.b_setHp(hp)
        return "{}'s laff has been set to {}.".format(toon.getName(), hp)

class SetMaxHP(MagicWord):
    aliases = ["maxhp", "setmaxlaff", "maxlaff"]
    desc = "Sets the target's max laff."
    advancedDesc = "This Magic Word will change the maximum amount of laff points the target has to whichever value " \
                   "you specify. You are only allowed to specify a value between 15 and 137 laff points."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("maxhp", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        maxhp = args[0]

        if not 15 <= maxhp <= 137:
            return "Can't set {}'s max laff to {}! Specify a value between 15 and 137.".format(toon.getName(), maxhp)

        toon.b_setMaxHp(maxhp)
        toon.toonUp(maxhp)
        return "{}'s max laff has been set to {}.".format(toon.getName(), maxhp)

class ToggleOobe(MagicWord):
    aliases = ["oobe"]
    desc = "Toggles the out of body experience mode, which lets you move the camera freely."
    advancedDesc = "This Magic Word will toggle what is known as 'Out Of Body Experience' Mode, hence the name " \
                   "'Oobe'. When this mode is active, you are able to move the camera around with your mouse- " \
                   "though your camera will still follow your Toon."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        base.oobe()
        return "Oobe mode has been toggled."

class ToggleRun(MagicWord):
    aliases = ["run"]
    desc = "Toggles run mode, which gives you a faster running speed."
    advancedDesc = "This Magic Word will toggle Run Mode. When this mode is active, the target can run around at a " \
                   "very fast speed."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT

    def handleWord(self, invoker, avId, toon, *args):
        from direct.showbase.InputStateGlobal import inputState
        inputState.set('debugRunning', not inputState.isSet('debugRunning'))
        return "Run mode has been toggled."

class MaxToon(MagicWord):
    aliases = ["max", "idkfa"]
    desc = "Maxes your target toon."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toonbase import ToontownGlobals
        from toontown.quest import Quests
        from toontown.suit import SuitDNA
        from toontown.coghq import CogDisguiseGlobals

        # TODO: Handle this better, like giving out all awards, set the quest tier, stuff like that.
        # This is mainly copied from Anesidora just so I can better work on things.
        toon.b_setTrackAccess([1, 1, 1, 1, 1, 1, 1])

        toon.b_setMaxCarry(ToontownGlobals.MaxCarryLimit)
        toon.b_setQuestCarryLimit(ToontownGlobals.MaxQuestCarryLimit)

        toon.experience.maxOutExp()
        toon.d_setExperience(toon.experience.makeNetString())

        toon.inventory.maxOutInv()
        toon.d_setInventory(toon.inventory.makeNetString())

        toon.b_setMaxHp(ToontownGlobals.MaxHpLimit)
        toon.b_setHp(ToontownGlobals.MaxHpLimit)

        toon.b_setMaxMoney(250)
        toon.b_setMoney(toon.maxMoney)
        toon.b_setBankMoney(toon.maxBankMoney)

        toon.b_setQuests([])
        toon.b_setQuestCarryLimit(ToontownGlobals.MaxQuestCarryLimit)
        toon.b_setRewardHistory(Quests.LOOPING_FINAL_TIER, [])

        toon.b_setCogParts([*CogDisguiseGlobals.PartsPerSuitBitmasks])
        toon.b_setCogTypes([SuitDNA.suitsPerDept - 1] * 4)
        toon.b_setCogLevels([ToontownGlobals.MaxCogSuitLevel] * 4)

        return f"Successfully maxed {toon.getName()}!"
    
class Inventory(MagicWord):
    # by default restock the inventory
    aliases = ['gags', 'inv']
    desc = 'This allows you to modify your inventory in various ways.'
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("command", str, False, ''), ("track", str, False, ""), ("level", int, False, 0), ("amount", int, False, 0)]
    def handleWord(self, invoker, avId, toon, *args):
        command = args[0]
        # the list of words that can be used to restock the inventory
        restockInvWords = ['restock', 'max', 'all', '', 'fill']
        # the list of words that can be used to empty the inventory
        emptyInvWords = ['empty', 'zero', 'null', 'clear', 'none', 'reset']
        if command in restockInvWords:
            toon.inventory.maxOutInv()
            toon.d_setInventory(toon.inventory.makeNetString())
            return ("Maxing out inventory for " + toon.getName() + ".")
        if command in emptyInvWords:
            toon.inventory.zeroInv()
            toon.d_setInventory(toon.inventory.makeNetString())
            return ("Zeroing inventory for " + toon.getName() + ".")

class GagExp(MagicWord):
    # Sets exact experience on one gag track, rather than adding to it.
    aliases = ["trackexp"]
    desc = "Sets a Toon's experience on a single gag track."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("track", str, True), ("value", str, True)]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toonbase import ToontownBattleGlobals

        trackArg, valueArg = args[0], args[1]

        track = None
        if trackArg.lstrip('-').isdigit():
            track = int(trackArg)
        else:
            trackNames = [t.replace('-', '').lower() for t in ToontownBattleGlobals.Tracks]
            key = trackArg.replace('-', '').lower()
            if key in trackNames:
                track = trackNames.index(key)

        if track is None or track < 0 or track > ToontownBattleGlobals.MAX_TRACK_INDEX:
            return "Invalid track. Use an index 0-6 or a track name."

        levels = ToontownBattleGlobals.Levels[track]
        uberLevel = ToontownBattleGlobals.UBER_GAG_LEVEL_INDEX

        lowerValue = valueArg.lower()
        if lowerValue == "next":
            # One point below the next level's threshold crosses it on the next gag use.
            level = toon.experience.getExpLevel(track)
            value = levels[min(level + 1, uberLevel)] - 1
        elif lowerValue == "ubernext":
            value = levels[uberLevel] - 1
        else:
            try:
                value = int(valueArg)
            except ValueError:
                return "Value must be an integer, \"next\", or \"ubernext\"."

        value = max(0, min(value, ToontownBattleGlobals.MaxSkill))

        toon.experience.setExp(track, value)
        toon.d_setExperience(toon.experience.makeNetString())
        return f"Set {ToontownBattleGlobals.Tracks[track]} experience to {value} for {toon.getName()}."

class GameAccess(MagicWord):
    # Session-only: setAccess is `required ram`, not `db`, so this does not
    # persist across a reconnect. The class name lowercases to the "gameaccess"
    # alias; do not also list it in `aliases` (MagicWord.__init__ prepends the
    # class name automatically and a duplicate alias crashes on import).
    desc = "Sets the target's game access level for this session only (not saved to the database)."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("level", str, True)]

    _NAMES = {
        "full": OTPGlobals.AccessFull,
        "velvetrope": OTPGlobals.AccessVelvetRope,
    }

    def handleWord(self, invoker, avId, toon, *args):
        levelArg = args[0].lower()

        if levelArg in self._NAMES:
            level = self._NAMES[levelArg]
        elif levelArg.isdigit() and int(levelArg) in self._NAMES.values():
            level = int(levelArg)
        else:
            return "Invalid access level. Use one of: full, velvetrope, 2, 1."

        toon.setGameAccess(level)
        return "Set {}'s game access to {} for this session.".format(toon.getName(), levelArg)

class SetPinkSlips(MagicWord):
    # this command gives the target toon the specified amount of pink slips
    # default is 255
    aliases = ["pinkslips", "fires", 'setfires']
    desc = "Gives the target toon the specified amount of pink slips."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("amount", int, False, 255)]

    def handleWord(self, invoker, avId, toon, *args):
        toon.b_setPinkSlips(args[0])
        return f"Gave {toon.getName()} {args[0]} pink slips!"

class SetMoney(MagicWord):
    aliases = ["money"]
    desc = "Sets the amount of jellybeans in the target's pocket."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("money", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        money = args[0]

        if not 0 <= money <= toon.getMaxMoney():
            return "Can't set {0}'s jellybeans to {1}! Specify a value between 0 and {0}'s pocket size ({2}).".format(
                toon.getName(), money, toon.getMaxMoney())

        toon.b_setMoney(money)
        return "{}'s jellybeans have been set to {}.".format(toon.getName(), money)

class SetBankMoney(MagicWord):
    aliases = ["bank", "bankmoney"]
    desc = "Sets the amount of jellybeans in the target's bank."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("money", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        money = args[0]

        if not 0 <= money <= toon.getMaxBankMoney():
            return "Can't set {0}'s banked jellybeans to {1}! Specify a value between 0 and {0}'s bank size ({2}).".format(
                toon.getName(), money, toon.getMaxBankMoney())

        toon.b_setBankMoney(money)
        return "{}'s banked jellybeans have been set to {}.".format(toon.getName(), money)

class Deliver(MagicWord):
    desc = "Forces every catalog item currently on order to be delivered right now. Debug use only; has no effect on normal delivery timing."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        if not len(toon.onOrder):
            return "{} has nothing on order.".format(toon.getName())

        now = int(time.time() / 60 + 0.5)
        items = list(toon.onOrder)
        for item in items:
            item.deliveryDate = now
        count = len(items)

        toon.b_setBothSchedules(items, None)
        toon._DistributedToonAI__deliverBothPurchases(None)
        return "Delivered {} item(s) to {}.".format(count, toon.getName())

class Furnish(MagicWord):
    desc = "Debug use only: puts a gender-correct closet, a trunk and a bank into the target's house, plus a few plain items and a wallpaper/flooring/moulding/wainscoting/window set in the attic."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.catalog import CatalogItem
        from toontown.catalog.CatalogItemList import CatalogItemList
        from toontown.catalog.CatalogFurnitureItem import CatalogFurnitureItem, FLCloset, FLTrunk, FLBank
        from toontown.catalog.CatalogWallpaperItem import CatalogWallpaperItem
        from toontown.catalog.CatalogFlooringItem import CatalogFlooringItem
        from toontown.catalog.CatalogMouldingItem import CatalogMouldingItem
        from toontown.catalog.CatalogWainscotingItem import CatalogWainscotingItem
        from toontown.catalog.CatalogWindowItem import CatalogWindowItem

        houseId = toon.getHouseId()
        if not houseId:
            return "{} has no house.".format(toon.getName())

        forBoys = toon.getStyle().getGender() == 'm'
        closetType = 500 if forBoys else 510
        trunkType = 4000 if forBoys else 4010
        bankType = 1300

        closet = CatalogFurnitureItem(closetType, posHpr=(4, 0, 0, 90, 0, 0))
        trunk = CatalogFurnitureItem(trunkType, posHpr=(-4, 0, 0, -90, 0, 0))
        bank = CatalogFurnitureItem(bankType, posHpr=(0, 4, 0, 0, 0, 0))
        atticItems = [CatalogFurnitureItem(100) for i in range(3)]
        candidates = ((closet, FLCloset, 'closet'), (trunk, FLTrunk, 'trunk'), (bank, FLBank, 'bank'))

        # One of each surface kind, plus a window, so the wallpaper/window
        # pickers in furniture mode (toontown/estate/houseDesign.py:1007-1015)
        # have something to bring in from the attic.
        atticWallpaperItems = [CatalogWallpaperItem(1000, 0), CatalogFlooringItem(1000, 0),
            CatalogMouldingItem(1000, 0), CatalogWainscotingItem(1000, 0)]
        atticWindowItems = [CatalogWindowItem(10), CatalogWindowItem(20)]

        house = self.air.doId2do.get(houseId)
        addedNames = []
        skippedNames = []
        addedAtticCount = len(atticItems)
        skippedAtticCount = 0
        addedWallpaperCount = len(atticWallpaperItems)
        skippedWallpaperCount = 0
        addedWindowCount = len(atticWindowItems)
        skippedWindowCount = 0
        if house is not None:
            interior = house.getInteriorItemList()
            existingFlags = 0
            for existingItem in interior:
                existingFlags |= existingItem.getFlags()

            startIndex = len(interior)
            toAdd = []
            for item, flag, name in candidates:
                if existingFlags & flag:
                    skippedNames.append(name)
                else:
                    interior.append(item)
                    toAdd.append(item)
                    addedNames.append(name)
            if toAdd:
                house.setInteriorItemList(interior)

            existingAttic = house.getAtticItemList()
            newAtticItems = [item for item in atticItems
                             if not any(item.compareTo(existing) == 0 for existing in existingAttic)]
            addedAtticCount = len(newAtticItems)
            skippedAtticCount = len(atticItems) - addedAtticCount

            # createFurniture (DistributedFurnitureManagerAI.py:412-426) only
            # runs once, when the house's interior is first generated -- a
            # house that already has its interior up needs the new items'
            # DOs generated directly, or the room stays bare even though the
            # blob above now has them in it.
            furnitureMgr = getattr(house, 'furnitureMgr', None)
            if newAtticItems:
                if furnitureMgr is not None:
                    # setAtticItems is broadcast on the manager but only db
                    # on the house itself (etc/toon.dc:1212 vs 2090), so
                    # writing through house.addAtticItem never reaches a
                    # client already in furniture mode -- go through the
                    # manager instead, the same way its own attic mutators do.
                    attic = house.getAtticItemList()
                    for item in newAtticItems:
                        attic.append(item)
                    furnitureMgr.b_setAtticItems(attic.getBlob())
                else:
                    for item in newAtticItems:
                        house.addAtticItem(item)
            if furnitureMgr is not None:
                for offset, item in enumerate(toAdd):
                    furnitureMgr.generateInteriorItem(item, startIndex + offset)

            existingWallpaper = house.getAtticWallpaperList()
            newWallpaperItems = [item for item in atticWallpaperItems
                                  if not any(item.compareTo(existing) == 0 for existing in existingWallpaper)]
            addedWallpaperCount = len(newWallpaperItems)
            skippedWallpaperCount = len(atticWallpaperItems) - addedWallpaperCount
            if newWallpaperItems:
                if furnitureMgr is not None:
                    wallpaper = house.getAtticWallpaperList()
                    for item in newWallpaperItems:
                        wallpaper.append(item)
                    furnitureMgr.b_setAtticWallpaper(wallpaper.getBlob())
                else:
                    for item in newWallpaperItems:
                        house.addWallpaper(item)

            existingWindows = house.getAtticWindowList()
            newWindowItems = [item for item in atticWindowItems
                               if not any(item.compareTo(existing) == 0 for existing in existingWindows)]
            addedWindowCount = len(newWindowItems)
            skippedWindowCount = len(atticWindowItems) - addedWindowCount
            if newWindowItems:
                if furnitureMgr is not None:
                    windows = house.getAtticWindowList()
                    for item in newWindowItems:
                        windows.append(item)
                    furnitureMgr.b_setAtticWindows(windows.getBlob())
                else:
                    for item in newWindowItems:
                        house.addWindow(item)
        else:
            # The house isn't generated on this AI (the target isn't inside
            # their own estate right now), so there's no live object to call
            # -- write the two blobs straight to its database row instead,
            # the same field-write path AstronLoginManagerUD.py:253 uses for
            # an object that isn't resident either. This replaces whatever
            # was already in those two blobs rather than merging into it, so
            # there is nothing to compare against for skipping here.
            addedNames = [name for _, _, name in candidates]
            interior = CatalogItemList(store=CatalogItem.Customization | CatalogItem.Location)
            for item in (closet, trunk, bank):
                interior.append(item)
            attic = CatalogItemList(store=CatalogItem.Customization)
            for item in atticItems:
                attic.append(item)
            wallpaper = CatalogItemList(store=CatalogItem.Customization)
            for item in atticWallpaperItems:
                wallpaper.append(item)
            windows = CatalogItemList(store=CatalogItem.Customization)
            for item in atticWindowItems:
                windows.append(item)

            dclass = self.air.dclassesByName['DistributedHouseAI']
            self.air.dbInterface.updateObject(
                self.air.dbId, houseId, dclass,
                {'setInteriorItems': (interior.getBlob(),),
                 'setAtticItems': (attic.getBlob(),),
                 'setAtticWallpaper': (wallpaper.getBlob(),),
                 'setAtticWindows': (windows.getBlob(),)})

        # recordPurchase (CatalogFurnitureItem.py:1022-1034) raises these to
        # match the furniture it just delivered; ~max does not touch them.
        toon.b_setMaxClothes(closet.getMaxClothes())
        toon.b_setMaxAccessories(trunk.getMaxAccessories())
        toon.b_setMaxBankMoney(bank.getMaxBankMoney())

        message = "Furnished {}'s house".format(toon.getName())
        if addedNames:
            message += " with a {}".format(', a '.join(addedNames))
        message += (", plus {} attic item(s), {} attic wallpaper item(s) "
                     "and {} attic window item(s)").format(
            addedAtticCount, addedWallpaperCount, addedWindowCount)
        if skippedNames or skippedAtticCount or skippedWallpaperCount or skippedWindowCount:
            skipParts = list(skippedNames)
            if skippedAtticCount:
                skipParts.append("{} attic item(s)".format(skippedAtticCount))
            if skippedWallpaperCount:
                skipParts.append("{} attic wallpaper item(s)".format(skippedWallpaperCount))
            if skippedWindowCount:
                skipParts.append("{} attic window item(s)".format(skippedWindowCount))
            message += " (already had {}, skipped)".format(', '.join(skipParts))
        return message + "."

class Wardrobe(MagicWord):
    desc = "Debug use only: adds gender-correct tops and bottoms to the target's closet lists until it owns at least count of each."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("count", int, False, 2)]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toon import ToonDNA

        count = args[0]
        if not 1 <= count <= 255:
            return "Specify a count between 1 and 255."

        # DistributedNPCTailorAI.setDNA (:126-144) only grants a garment
        # through a ClothingTicket or 'free-clothes', so a toon otherwise
        # owns nothing but the outfit it is wearing (clothesTopsList /
        # clothesBottomsList stay empty). Reuse Furnish's gender lookup
        # (getStyle().getGender()) so the seeded pieces fit the avatar.
        gender = toon.getStyle().getGender()

        topsList = list(toon.getClothesTopsList())
        ownedTops = set(tuple(topsList[i:i + 4]) for i in range(0, len(topsList), 4))
        addedTops = 0
        attempts = 0
        while len(ownedTops) < count and attempts < count * 20:
            attempts += 1
            top = ToonDNA.getRandomTop(gender)
            if top in ownedTops:
                continue
            ownedTops.add(top)
            topsList.extend(top)
            addedTops += 1

        bottomsList = list(toon.getClothesBottomsList())
        ownedBottoms = set(tuple(bottomsList[i:i + 2]) for i in range(0, len(bottomsList), 2))
        addedBottoms = 0
        attempts = 0
        while len(ownedBottoms) < count and attempts < count * 20:
            attempts += 1
            bottom = ToonDNA.getRandomBottom(gender)
            if bottom in ownedBottoms:
                continue
            ownedBottoms.add(bottom)
            bottomsList.extend(bottom)
            addedBottoms += 1

        needed = len(topsList) // 4 + len(bottomsList) // 2
        if needed > toon.getMaxClothes():
            toon.b_setMaxClothes(needed)

        if addedTops:
            toon.b_setClothesTopsList(topsList)
        if addedBottoms:
            toon.b_setClothesBottomsList(bottomsList)

        return "{} now owns {} top(s) and {} bottom(s) ({} top(s), {} bottom(s) added).".format(
            toon.getName(), len(ownedTops), len(ownedBottoms), addedTops, addedBottoms)

class Disguise(MagicWord):
    aliases = ["cogsuit"]
    desc = "Gives the target a complete cog disguise for one department and unlocks the disguise page."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("dept", str, False, 'sell'), ("level", int, False, 1)]

    # SuitDNA.suitDepts order: c, l, m, s
    deptNames = {'c': ('c', 'boss', 'bossbot'),
                 'l': ('l', 'law', 'lawbot'),
                 'm': ('m', 'cash', 'cashbot'),
                 's': ('s', 'sell', 'sellbot')}

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.suit import SuitDNA
        from toontown.coghq import CogDisguiseGlobals

        deptName = args[0].lower()
        level = args[1]
        dept = None
        for deptChar, names in self.deptNames.items():
            if deptName in names:
                dept = deptChar
                break
        if dept is None:
            return f"Unknown department \"{args[0]}\". Valid departments: boss, law, cash, sell."
        if not 1 <= level <= 5:
            return "Specify a suit level between 1 and 5."

        deptIndex = SuitDNA.suitDepts.index(dept)
        parts = list(toon.getCogParts())
        parts[deptIndex] = CogDisguiseGlobals.PartsPerSuitBitmasks[deptIndex]
        toon.b_setCogParts(parts)
        types = list(toon.getCogTypes())
        types[deptIndex] = 0
        toon.b_setCogTypes(types)
        # cogLevels holds the absolute level; the first cog type of every department is level 0 (type level 1).
        levels = list(toon.getCogLevels())
        levels[deptIndex] = level - 1
        toon.b_setCogLevels(levels)
        merits = list(toon.getCogMerits())
        merits[deptIndex] = CogDisguiseGlobals.getTotalMerits(toon, deptIndex) // 2
        toon.b_setCogMerits(merits)
        toon.b_setDisguisePageFlag(1)
        return f"Gave {toon.getName()} a level {level} {SuitDNA.suitDeptFullnames[dept]} disguise."

class Sos(MagicWord):
    aliases = ["soscards"]
    desc = "Gives the target a few SOS cards and unlocks the SOS page."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("count", int, False, 2)]

    # One NPC per track from NPCToons.HQnpcFriends: toon-up, trap, lure, sound, drop.
    npcIds = (2001, 2011, 3112, 4119, 1116)

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toon import NPCToons

        count = args[0]
        if not 1 <= count <= 255:
            return "Specify a card count between 1 and 255."

        friends = [(npcId, count) for npcId in self.npcIds if npcId in NPCToons.npcFriends]
        toon.b_setNPCFriendsDict(friends)
        toon.b_setSosPageFlag(1)
        return f"Gave {toon.getName()} {len(friends)} SOS cards x{count}."

class Kart(MagicWord):
    aliases = ["givekart"]
    desc = "Gives the target a kart (so the kart page appears) and some tickets."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("bodyType", int, False, 0), ("tickets", int, False, 500)]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.racing import KartDNA

        bodyType = args[0]
        tickets = args[1]
        if not simbase.wantKarts:
            return "Karts are disabled on this AI (wantKarts)."
        if bodyType not in KartDNA.KartDict:
            return f"Unknown kart body type {bodyType}. Valid types: {list(KartDNA.KartDict.keys())}"
        if tickets < 0:
            return "Specify a non-negative ticket count."

        toon.b_setKartBodyType(bodyType)
        toon.b_setTickets(tickets)
        return f"Gave {toon.getName()} kart {bodyType} and {toon.getTickets()} tickets."

class Golf(MagicWord):
    aliases = ["golfhistory"]
    desc = "Gives the target a golf history (so the golf page appears)."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'

    # Indexed by GolfGlobals.CoursesCompleted .. CourseTwoWins (NumHistory entries).
    history = [5, 2, 1, 2, 3, 6, 6, 1, 1, 1]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.golf import GolfGlobals

        # setGolfHistory is a fixed-length uint16[18] dc field (etc/toon.dc),
        # longer than GolfGlobals.NumHistory, so overlay the toon's current
        # (already correctly sized) history instead of building a new list.
        history = list(toon.getGolfHistory())
        for i, value in enumerate(self.history[:GolfGlobals.NumHistory]):
            history[i] = value
        toon.b_setGolfHistory(history)
        return f"Gave {toon.getName()} a golf history ({sum(toon.getGolfTrophies())} trophies)."

def _findEstateManager(air):
    from toontown.estate.EstateManagerAI import EstateManagerAI
    for do in air.doId2do.values():
        if isinstance(do, EstateManagerAI):
            return do
    return None


def _residentHouse(air, toon):
    """The toon's own house and its estate while that estate is live, found
    through the estate manager's `worlds` map (EstateManagerAI.py:17-19).
    `(None, None)` if the toon is not resident in a live estate."""
    accountId = getattr(toon, 'DISLid', None)
    if not accountId:
        return (None, None)
    estateMgr = _findEstateManager(air)
    if estateMgr is None:
        return (None, None)
    world = estateMgr.worlds.get(accountId)
    if world is None or world.estate is None:
        return (None, None)
    for house in world.houses:
        if house.avatarId == toon.doId:
            return (house, world.estate)
    return (None, None)


def _residentWorld(air, toon):
    """The live `EstateWorld` for the toon's own account, the same `worlds`
    map `_residentHouse` reads -- without requiring a house match, since the
    fireworks cannon and its show are estate-wide props, not per-house
    ones.  `None` if the toon is not resident in a live estate."""
    accountId = getattr(toon, 'DISLid', None)
    if not accountId:
        return None
    estateMgr = _findEstateManager(air)
    if estateMgr is None:
        return None
    world = estateMgr.worlds.get(accountId)
    if world is None or world.estate is None:
        return None
    return world


class Cannon(MagicWord):
    desc = ("Turns on the invoker's pinball cannon and drops it, with the target it "
            "shoots at, into the estate the invoker is standing in.  This only enables "
            "one house's cannon for the current visit; see ~rental for the real "
            "estate-wide rental path (every house's cannon, persisted, and it expires).")
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'

    def handleWord(self, invoker, avId, toon, *args):
        if not toon.getHouseId():
            return "{} has no house.".format(toon.getName())

        house, estateAI = _residentHouse(self.air, toon)
        if house is None:
            return "{} is not standing in their own live estate.".format(toon.getName())

        # setCannonEnabled is `required` only (etc/toon.dc:1219) -- no `db`,
        # so the flag lives as long as the house object does and the cannon
        # has to be generated now rather than on the next visit home.
        house.setCannonEnabled(1)
        house.createCannon(estateAI)
        if house.cannon is None:
            return "{}'s cannon could not be generated.".format(toon.getName())
        return "Dropped a cannon in {}'s estate.".format(toon.getName())


class Rental(MagicWord):
    desc = ("Rents the invoker's estate cannon or game table for a number of hours "
            "(default 1) -- the same rentItem CatalogRentalItem.recordPurchase calls, "
            "not a parallel path.  'gametable' is stored and expires correctly but "
            "generates no DO (no game-table object exists yet).  '~rental expire' forces "
            "the current rental's clock to now instead of waiting out the real deadline.")
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("command", str, False, ''), ("hours", str, False, '')]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toonbase import ToontownGlobals

        command = (args[0] if len(args) > 0 else '') or ''
        command = str(command).strip().lower()
        hoursArg = (args[1] if len(args) > 1 else '') or ''

        if not toon.getHouseId():
            return "{} has no house.".format(toon.getName())

        house, estateAI = _residentHouse(self.air, toon)
        if house is None:
            return "{} is not standing in their own live estate.".format(toon.getName())

        if command == 'expire':
            estateAI.forceExpireRental()
            return "Expired {}'s estate rental.".format(toon.getName())

        rentalTypes = {'cannon': ToontownGlobals.RentalCannon,
                      'gametable': ToontownGlobals.RentalGameTable}
        if command not in rentalTypes:
            return "Specify a rental type: cannon or gametable (or 'expire')."

        try:
            hours = float(hoursArg) if hoursArg else 1.0
        except ValueError:
            return "Specify a number of hours."

        estateAI.rentItem(rentalTypes[command], int(hours * 60))
        return "Rented {} a {} for {} hour(s).".format(toon.getName(), command, hours)


_flowerVarietyPairsCache = None


def _flowerVarietyPairs():
    """Every valid (species, varietyIndex) pair for flower species in
    GardenGlobals.PlantAttributes, species then variety index ascending.
    `variety` is the 0-based index into PlantAttributes[species]['varieties'],
    the same value FlowerBase.getValue and GardenGlobals.getFlowerVarietyName /
    getNumBeansRequired expect -- not a recipe id."""
    global _flowerVarietyPairsCache
    if _flowerVarietyPairsCache is None:
        from toontown.estate import GardenGlobals
        pairs = []
        for species in sorted(GardenGlobals.PlantAttributes):
            attrib = GardenGlobals.PlantAttributes[species]
            if attrib['plantType'] != GardenGlobals.FLOWER_TYPE:
                continue
            for variety in range(len(attrib['varieties'])):
                pairs.append((species, variety))
        _flowerVarietyPairsCache = tuple(pairs)
    return _flowerVarietyPairsCache


class Garden(MagicWord):
    aliases = ["gardenstarted"]
    desc = ("Marks the target's garden as started (so the garden page appears), with shovel "
            "skill and a few flowers. Sub-commands seed garden state without waiting real "
            "days: 'plant flower|tree|statuary' plants a default into the first empty "
            "matching plot of the invoker's own estate, 'grow [level]' maxes every currently "
            "planted item's growth and water levels, 'reset' empties every planted hard "
            "point back to a bare plot, 'collection <n>' sets the flower collection to "
            "exactly n distinct varieties without touching the flower basket.")
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("command", str, False, ''), ("option", str, False, '')]

    # `~garden plant` defaults -- species 49 variety index 0 is recipe 10
    # (GardenGlobals.py:92,358-359), a single-bean flower; track/level 0 is
    # always unlocked; species 200 is the toon statuary whose special (100)
    # is the cheapest garden special (GardenGlobals.py:212-216,428-429).
    PLANT_FLOWER_SPECIES = 49
    PLANT_FLOWER_VARIETY = 0
    PLANT_TREE_TRACK = 0
    PLANT_TREE_LEVEL = 0
    PLANT_STATUARY_SPECIES = 200
    PLANT_STATUARY_SPECIAL = 100

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.estate import GardenGlobals

        command = (args[0] if len(args) > 0 else '') or ''
        option = (args[1] if len(args) > 1 else '') or ''
        command = str(command).strip().lower()
        option = str(option).strip().lower()

        if command == 'plant':
            return self._plant(toon, option)
        if command == 'grow':
            return self._grow(toon, option)
        if command == 'reset':
            return self._reset(toon)
        if command == 'collection':
            return self._collection(toon, option)

        # Plain `~garden [shovelSkill]` -- unchanged from before this task.
        try:
            shovelSkill = int(command) if command else 40
        except ValueError:
            return "Specify a shovel skill below the next shovel's skill points."
        if not 0 <= shovelSkill < GardenGlobals.ShovelAttributes[toon.getShovel()]['skillPts']:
            return "Specify a shovel skill below the next shovel's skill points ({}).".format(
                GardenGlobals.ShovelAttributes[toon.getShovel()]['skillPts'])

        flowers = _flowerVarietyPairs()[:3]
        for species, variety in flowers:
            if variety >= len(GardenGlobals.PlantAttributes[species]['varieties']):
                return f"Bad flower variety {variety} for species {species}."

        toon.b_setGardenStarted(1)
        toon.b_setShovelSkill(shovelSkill)
        toon.b_setFlowerCollection([f[0] for f in flowers], [f[1] for f in flowers])
        return f"Started {toon.getName()}'s garden with {len(flowers)} flowers and shovel skill {shovelSkill}."

    def _collection(self, toon, option):
        pairs = _flowerVarietyPairs()
        try:
            count = int(option) if option else 0
        except ValueError:
            return "Specify a flower collection count between 0 and {}.".format(len(pairs))
        if not 0 <= count <= len(pairs):
            return "Specify a flower collection count between 0 and {}.".format(len(pairs))

        chosen = pairs[:count]
        toon.b_setFlowerCollection([f[0] for f in chosen], [f[1] for f in chosen])
        return "Set {}'s flower collection to {} distinct variet{}.".format(
            toon.getName(), count, 'y' if count == 1 else 'ies')

    def _residentHouse(self, toon):
        """The invoker's own live house and estate, once its garden has been
        generated -- `(None, None)` otherwise."""
        house, estateAI = _residentHouse(self.air, toon)
        if house is None or not (house.gardenPlots or house.gardenPlants):
            return (None, None)
        return (house, estateAI)

    def _livePlots(self, house, estateAI):
        # Scans live DOs rather than house.gardenPlots -- B6's own
        # _removeFromGarden (DistributedLawnDecorAI.py:95-112) regenerates a
        # plot without appending it back to the house's bookkeeping list, so
        # that list can go stale after any plant/harvest/reset.
        from toontown.estate.DistributedGardenPlotAI import DistributedGardenPlotAI
        return [do for do in self.air.doId2do.values()
                if isinstance(do, DistributedGardenPlotAI) and do.estateAI is estateAI
                and do.ownerIndex == house.gardenPos]

    def _livePlants(self, house, estateAI):
        from toontown.estate.DistributedGardenPlotAI import DistributedGardenPlotAI
        from toontown.estate.DistributedGardenBoxAI import DistributedGardenBoxAI
        from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI
        return [do for do in self.air.doId2do.values()
                if isinstance(do, DistributedLawnDecorAI)
                and not isinstance(do, (DistributedGardenPlotAI, DistributedGardenBoxAI))
                and do.estateAI is estateAI and do.ownerIndex == house.gardenPos]

    def _plotFor(self, house, estateAI, wantedType):
        from toontown.estate import GardenGlobals
        for plot in self._livePlots(house, estateAI):
            if GardenGlobals.whatCanBePlanted(house.gardenPos, plot.getPlot()) == wantedType:
                return plot
        return None

    def _plant(self, toon, option):
        from toontown.estate import GardenGlobals

        house, estateAI = self._residentHouse(toon)
        if house is None:
            return "{} is not resident in a live estate with a garden.".format(toon.getName())

        if option == 'flower':
            plot = self._plotFor(house, estateAI, GardenGlobals.FLOWER_TYPE)
            if plot is None:
                return "{} has no empty flower plot.".format(toon.getName())
            numBeans = GardenGlobals.getNumBeansRequired(self.PLANT_FLOWER_SPECIES, self.PLANT_FLOWER_VARIETY)
            if numBeans < 0 or toon.getMoney() + toon.getBankMoney() < numBeans:
                return "{} cannot afford a flower ({} beans needed) -- run ~money first.".format(
                    toon.getName(), numBeans)
            plot.plotEntered()
            plot.plantFlower(self.PLANT_FLOWER_SPECIES, self.PLANT_FLOWER_VARIETY)
            return "Planted a flower in {}'s garden.".format(toon.getName())

        if option == 'tree':
            plot = self._plotFor(house, estateAI, GardenGlobals.GAG_TREE_TYPE)
            if plot is None:
                return "{} has no empty gag tree plot.".format(toon.getName())
            inventory = getattr(toon, 'inventory', None)
            if inventory is None:
                return "{} has no inventory.".format(toon.getName())
            if inventory.numItem(self.PLANT_TREE_TRACK, self.PLANT_TREE_LEVEL) <= 0:
                # addItems (InventoryBase.py:95-114) silently returns 0 with
                # no exception when the toon lacks track access -- grant it
                # first (a fresh login:bootstrap_fresh_avatar toon has none)
                # and still check the return value before planting.
                if not toon.hasTrackAccess(self.PLANT_TREE_TRACK):
                    toon.addTrackAccess(self.PLANT_TREE_TRACK)
                if not inventory.addItem(self.PLANT_TREE_TRACK, self.PLANT_TREE_LEVEL):
                    return "{} could not be granted a gag tree gag.".format(toon.getName())
                toon.b_setInventory(inventory.makeNetString())
            plot.plotEntered()
            plot.plantGagTree(self.PLANT_TREE_TRACK, self.PLANT_TREE_LEVEL)
            return "Planted a gag tree in {}'s garden.".format(toon.getName())

        if option == 'statuary':
            plot = self._plotFor(house, estateAI, GardenGlobals.STATUARY_TYPE)
            if plot is None:
                return "{} has no empty statuary plot.".format(toon.getName())
            hasSpecial = any(index == self.PLANT_STATUARY_SPECIAL and count > 0
                             for index, count in toon.getGardenSpecials())
            if not hasSpecial:
                toon.addGardenItem(self.PLANT_STATUARY_SPECIAL, 1)
            plot.plotEntered()
            plot.plantStatuary(self.PLANT_STATUARY_SPECIES)
            return "Planted a statuary in {}'s garden.".format(toon.getName())

        return "Specify ~garden plant flower, tree, or statuary."

    def _grow(self, toon, option):
        house, estateAI = self._residentHouse(toon)
        if house is None:
            return "{} is not resident in a live estate with a garden.".format(toon.getName())

        level = None
        if option:
            try:
                level = int(option)
            except ValueError:
                return "Specify a numeric growth level."

        count = 0
        for plant in self._livePlants(house, estateAI):
            if not hasattr(plant, 'growthThresholds'):
                continue  # statuary has no growth stages -- always fully grown
            growthLevel = level if level is not None else plant.growthThresholds[2]
            plant.setGrowthLevel(growthLevel)
            plant.d_setGrowthLevel(growthLevel)
            plant.setWaterLevel(plant.maxWaterLevel)
            plant.d_setWaterLevel(plant.maxWaterLevel)
            plant._persistLevels()
            count += 1
        return "Grew {} plant(s) in {}'s garden.".format(count, toon.getName())

    def _reset(self, toon):
        house, estateAI = self._residentHouse(toon)
        if house is None:
            return "{} is not resident in a live estate with a garden.".format(toon.getName())

        count = 0
        for plant in self._livePlants(house, estateAI):
            plant._removeFromGarden()
            count += 1
        return "Reset {} plant(s) in {}'s garden back to empty plots.".format(count, toon.getName())

class Trophies(MagicWord):
    desc = ("Sets the target's garden trophies directly, skipping the flower-collection grind. "
            "Give a count 0-4 to award that many trophy ids in order; omit it to award all four.")
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("count", str, False, '')]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.estate import GardenGlobals

        raw = (args[0] if len(args) > 0 else '') or ''
        raw = str(raw).strip()
        numTrophies = len(GardenGlobals.TrophyDict)
        try:
            count = int(raw) if raw else numTrophies
        except ValueError:
            return "Specify a trophy count between 0 and {}.".format(numTrophies)
        if not 0 <= count <= numTrophies:
            return "Specify a trophy count between 0 and {}.".format(numTrophies)

        trophies = list(range(count))
        toon.b_setGardenTrophies(trophies)
        return "Set {}'s garden trophies to {}.".format(toon.getName(), trophies)

class Flowers(MagicWord):
    desc = ("Fills the target's flower basket with n flowers (the sale's input, distinct from "
            "the flower collection ~garden seeds) without a real pick.")
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("count", str, False, '')]

    def handleWord(self, invoker, avId, toon, *args):
        raw = (args[0] if len(args) > 0 else '') or ''
        raw = str(raw).strip()
        try:
            count = int(raw) if raw else 5
        except ValueError:
            return "Specify a non-negative number of flowers."
        if count < 0:
            return "Specify a non-negative number of flowers."

        flowers = _flowerVarietyPairs()
        maxBasket = toon.getMaxFlowerBasket() if hasattr(toon, 'getMaxFlowerBasket') else count
        count = min(count, maxBasket)
        speciesList = [flowers[i % len(flowers)][0] for i in range(count)]
        varietyList = [flowers[i % len(flowers)][1] for i in range(count)]
        toon.b_setFlowerBasket(speciesList, varietyList)
        return "Filled {}'s flower basket with {} flower(s).".format(toon.getName(), count)

class Fish(MagicWord):
    aliases = ["givefish"]
    desc = "Puts a few fish in the target's bucket and records a fish collection (with the first trophy)."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("tank", int, False, 4), ("collection", int, False, 10)]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.fishing import FishGlobals

        numTank = args[0]
        numCollection = args[1]
        if not 0 <= numTank <= toon.getMaxFishTank():
            return f"Specify a bucket count between 0 and {toon.getMaxFishTank()}."
        if not 1 <= numCollection <= FishGlobals.getTotalNumFish():
            return f"Specify a collection size between 1 and {FishGlobals.getTotalNumFish()}."

        # Walk the fish table in order so the same word always gives the same fish;
        # weights (ounces) sit mid-way through each species' range.
        fish = []
        for genus in FishGlobals.getGenera():
            for species in range(len(FishGlobals.getSpecies(genus))):
                minWeight, maxWeight = FishGlobals.getWeightRange(genus, species)
                fish.append((genus, species, int(round((minWeight + maxWeight) / 2.0 * 16))))
        collection = fish[:numCollection]
        tank = fish[:numTank]
        toon.b_setFishCollection([f[0] for f in collection], [f[1] for f in collection], [f[2] for f in collection])
        toon.b_setFishTank([f[0] for f in tank], [f[1] for f in tank], [f[2] for f in tank])
        trophies = list(range(len(collection) // FishGlobals.FISH_PER_BONUS))
        toon.b_setFishingTrophies(trophies)
        return f"Gave {toon.getName()} {len(tank)} fish in the bucket, {len(collection)} in the collection, {len(trophies)} trophies."

class AbortMinigame(MagicWord):
    aliases = ["exitgame", "exitminigame", "quitgame", "quitminigame", "skipgame", "skipminigame"]
    desc = "Aborts an ongoing minigame."
    execLocation = MagicWordConfig.EXEC_LOC_CLIENT
    arguments = []

    def handleWord(self, invoker, avId, toon, *args):
        messenger.send("minigameAbort")
        return "Requested minigame abort."  

class SkipMiniGolfHole(MagicWord):
    aliases = ["skipgolfhole", "skipgolf", "skiphole"]
    desc = "Skips the current golf hole."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = []

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.golf.DistributedGolfCourseAI import DistributedGolfCourseAI
        course = None
        for do in simbase.air.doId2do.values(): # For all doids, check whether it's a golf course, then check if our target is part of it.
            if isinstance(do, DistributedGolfCourseAI):
                if invoker.doId in do.avIdList:
                    course = do
                    break
        if not course:
            return "You aren't in a golf course!"

        if course.isPlayingLastHole(): # If the Toon is on the final hole, calling holeOver() will softlock, so instead we move onto the reward screen.
            course.demand('WaitReward')
        else:
            course.holeOver()

        return "Skipped the current hole."
    
class AbortGolfCourse(MagicWord):
    aliases = ["abortminigolf", "abortgolf", "abortcourse", "leavegolf", "leavecourse"]
    desc = "Aborts the current golf course."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = []

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.golf.DistributedGolfCourseAI import DistributedGolfCourseAI
        course = None
        for do in simbase.air.doId2do.values(): # For all doids, check whether it's a golf course, then check if our target is part of it.
            if isinstance(do, DistributedGolfCourseAI):
                if invoker.doId in do.avIdList:
                    course = do
                    break
        if not course:
            return "You aren't in a golf course!"
        
        course.setCourseAbort()

        return "Aborted golf course."

class Minigame(MagicWord):
    aliases = ["mg"]
    desc = "Teleport to or request the next trolley minigame."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("command", str, True), ("minigame", str, False, ''), ("difficulty", float, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        command = args[0]
        minigame = args[1]
        difficulty = args[2]

        from toontown.toonbase import ToontownGlobals
        from toontown.hood import ZoneUtil
        from toontown.minigame import MinigameCreatorAI
        if command in ToontownGlobals.MinigameNames:
            # Shortcut
            minigame = args[0]
            try:
                difficulty = float(args[2])
            except ValueError:
                difficulty = 0
            
            if toon.zoneId in MinigameCreatorAI.MinigameZoneRefs:
                # Already in minigame zone, assume request
                command = "request"
            elif toon.zoneId == ZoneUtil.getSafeZoneId(toon.zoneId):
                # Assume teleport
                command = "teleport"
            else:
                # Request by default
                command = "request"
        
        isTeleport = command in ('teleport', 'tp')
        isRequest = command in ('request', 'next')

        mgId = None
        mgDiff = None if difficulty == 0 else difficulty
        mgKeep = None
        mgSzId = ZoneUtil.getSafeZoneId(toon.zoneId) if isTeleport else None

        if not any ((isTeleport, isRequest)):
            return f"Unknown command or minigame \"{command}\".  Valid commands: \"teleport\", \"request\", or a minigame to automatically teleport or request"

        try:
            mgId = int(minigame)
            if mgId not in ToontownGlobals.MinigameIDs:
                return f"Unknown minigame ID {mgId}."
        except:
            if minigame not in ToontownGlobals.MinigameNames:
                return f"Unknown minigame name \"{minigame}\"."
            mgId = ToontownGlobals.MinigameNames.get(minigame)

        if any((isTeleport, isRequest)):
            if isTeleport:
                if ZoneUtil.isDynamicZone(toon.zoneId) or not toon.zoneId == mgSzId:
                    return "Target needs to be in a playground to teleport to a minigame."
                mgSzId = ToontownGlobals.ToontownCentral if ZoneUtil.isWelcomeValley(mgSzId) else mgSzId
            MinigameCreatorAI.RequestMinigame[avId] = (mgId, mgKeep, mgDiff, mgSzId)
            if isTeleport:
                try:
                    result = MinigameCreatorAI.createMinigame(self.air, [avId], mgSzId)
                except:
                    return f"Unable to create \"{minigame}\" minigame"
        
                minigameZone = result['minigameZone']
                retStr =  f"Teleporting {toon.getName()} to minigame \"{minigame}\""
                if mgDiff:
                    retStr += f" with difficulty {mgDiff}"
                return retStr + "...", avId, ["minigame", "minigame", "", mgSzId, minigameZone, 0]

            # isRequest
            retStr = f"Successfully requested minigame \"{minigame}\""
            if mgDiff:
                retStr += f" with difficulty {mgDiff}"
            return retStr + "."
        
        return f"Unknown command or minigame \"{command}\".  Valid commands: \"teleport\", \"request\", or a minigame to automatically teleport or request"

class Quests(MagicWord):
    aliases = ["quest", "tasks", "task", "toontasks"]
    desc = "Quest manupliation"
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("command", str, True), ("index", int, False, -1), ("progress", int, False, -1)]

    def handleWord(self, invoker, avId, toon, *args):
        command = args[0]
        index = args[1]
        progress = args[2]
        """
        Commands:
        - "finish": Finish a task (sets the progress to 1000), finishes all by default
        - "add" <questId> [progress]: dev/testing only (ot-dev, not upstream) --
          grants ToonTask <questId> directly (no NPC offer needed), optionally
          overwriting its progress. Used by the Panda capture harness to seed
          book:quests with filled QuestPosters (docs/PANDA_CAPTURE.md).
        """
        if command == "finish":
            if index == -1:
                self.air.questManager.completeAllQuestsMagically(toon)
                return "Finished all quests."
            else:
                if self.air.questManager.completeQuestMagically(toon, index):
                    return f"Finished quest {index}."
                return f"Quest {index} not found.  (Hint: Quest indexes start at 0)"
        elif command == "add":
            questId = index
            questProgress = None if progress < 0 else progress
            result = self.air.questManager.addQuestMagically(toon, questId, questProgress)
            if result is None:
                return f"Unknown questId {questId}."
            return f"Gave {toon.getName()} quest {questId}" + (f" (progress {questProgress})." if questProgress else ".")
        else:
            return "Valid commands: \"finish\", \"add\""

class Factory(MagicWord):
    desc = "Quickly start a Sellbot Factory."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [('sideEnterace', int, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        if not hasattr(self.air, "factoryMgr"):
            return "No factory manager."
        
        from toontown.toonbase import ToontownGlobals
        zoneId = self.air.factoryMgr.createFactory(ToontownGlobals.SellbotFactoryInt, 1 if args[0] > 0 else 0, [avId])
        return "Created factory, teleporting...", avId, ["cogHQLoader", "factoryInterior", "", ToontownGlobals.SellbotHQ, zoneId, 0]

class BossBattle(MagicWord):
    aliases = ["boss"]
    desc = "Create a new or manupliate the current boss battle."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("command", str, True), ("type", str, False, ""), ("start", int, False, 1)]

    def handleWord(self, invoker, avId, toon, *args):
        command = args[0].lower()
        type = args[1].lower()
        start = args[2]

        """
        Commands:
          - create [type] [start: 1]: Creates a boss and teleports to it.
          - start: Starts/Restarts the battle from the beginning.
          - stop: Stops the battle by going to the Frolic state.
          - skip: Skips the boss to the next state (needs getNextState to be implemented).
          - final: Skips the boss to the final round.
          - kill: Skips the boss to the Victory state.
        """

        # create command shortcut:
        if command in ("vp", "cfo", "cj", "ceo"):
            type = command
            command = "create"
            try:
                start = int(args[1])
            except ValueError:
                start = 1
        
        from toontown.suit.DistributedBossCogAI import AllBossCogs
        boss = None
        for bc in AllBossCogs:
            if bc.isToonKnown(invoker.doId):
                boss = bc
                break

        if command == "create":
            if boss:
                return "You're already in a boss battle.  Please finish this one."
            if type == "vp":
                from toontown.suit.DistributedSellbotBossAI import DistributedSellbotBossAI
                boss = DistributedSellbotBossAI(self.air)
            elif type == "cfo":
                from toontown.suit.DistributedCashbotBossAI import DistributedCashbotBossAI
                boss = DistributedCashbotBossAI(self.air)
            elif type == "cj":
                from toontown.suit.DistributedLawbotBossAI import DistributedLawbotBossAI
                boss = DistributedLawbotBossAI(self.air)
            elif type == "ceo":
                from toontown.suit.DistributedBossbotBossAI import DistributedBossbotBossAI
                boss = DistributedBossbotBossAI(self.air)
            else:
                return f"Unknown boss type: \"{type}\""
            
            zoneId = self.air.allocateZone()
            boss.generateWithRequired(zoneId)
            if start:
                boss.addToon(avId)
                boss.b_setState('WaitForToons')
            else:
                boss.b_setState('Frolic')
            
            self.acceptOnce(boss.uniqueName('BossDone'), self.__destroyBoss, extraArgs=[boss])

            respText = f"Created {type.upper()} boss battle"
            if not start:
                respText += " in Frolic state"

            return respText + ", teleporting...", toon.doId, ["cogHQLoader", "cogHQBossBattle", "movie" if start else "teleportIn", boss.getHoodId(), boss.zoneId, 0]
        
        elif command == "list":
            # List all the ongoing boss battles.
            dept2name = {'c': 'ceo',
                         'l': 'cj',
                         'm': 'cfo',
                         's': 'vp'}
            name2dept = invertDict(dept2name)

            if not AllBossCogs:
                return "No ongoing boss battles."
                
            respText = "\nBoss Battles:"

            if type:
                # Filter by boss type
                dept = name2dept.get(type)
                if not dept:
                    return f"Can't filter by unknown type \"{type.upper()}\""
                bossBattles = (boss for boss in AllBossCogs if boss.dept == dept)
            else:
                bossBattles = AllBossCogs

            for boss in bossBattles:
                index = AllBossCogs.index(boss)
                respText += f"\n - #{index}: {dept2name.get(boss.dept, '???').upper()}, {boss.zoneId}, {boss.state}, {len(boss.involvedToons)}"
            return respText
        
        elif command == "join":
            # Join an ongoing boss battle.
            if boss:
                return "You're already in a boss battle.  Please finish this one."
            try:
                index = int(type)
            except ValueError:
                return "Boss index not an integer!"
            
            if index not in range(len(AllBossCogs)):
                return "Index out of range!"
            
            boss = AllBossCogs[index]
            return "Teleporting to boss battle...", toon.doId, ["cogHQLoader", "cogHQBossBattle", "", boss.getHoodId(), boss.zoneId, 0]


        # The following commands needs the invoker to be in a boss battle.
        if not boss:
            return "You ain't in a boss battle!  Use the \"create\" command to create a boss battle."

        boss.acceptNewToons()
        if command == "start":
            boss.b_setState('WaitForToons')
            return "Boss battle started!"

        elif command == "stop":
            boss.b_setState("Frolic")
            return "Boss battle stopped!"

        elif command == "skip":
            try:
                nextState = boss.getNextState()
            except NotImplementedError:
                return "\"getNextState\" is not implemented for this boss battle!"
            if nextState:
                boss.b_setState(nextState)
                return f"Skipped to {nextState}!"
            return f"Cannot skip \"{boss.getCurrentOrNextState()}\" state."

        elif command in ("final", "pie", "crane"):
            if boss.dept == 'c':
                boss.b_setState("BattleFour")
            else:
                boss.b_setState("BattleThree")
            return "Skipped to final round!"

        elif command in ("kill", "victory", "finish"):
            boss.b_setState("Victory")
            return "Killed the boss!"

        # The create command is already described when the invoker is not in a battle.  These are the commands
        # they can use INSIDE the battle.
        return f"Unknown command: \"{command}\". Valid commands: \"start\", \"stop\", \"skip\", \"final\", \"kill\"."

    def __destroyBoss(self, boss):
        bossZone = boss.zoneId
        boss.requestDelete()
        self.air.deallocateZone(bossZone)

class GlobalTeleport(MagicWord):
    aliases = ["globaltp", "tpaccess"]
    desc = "Enables teleport access to all zones."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toonbase import ToontownGlobals
        toon.b_setHoodsVisited(ToontownGlobals.HoodsForTeleportAll)
        toon.b_setTeleportAccess(ToontownGlobals.HoodsForTeleportAll)
        return f"Enabled teleport access to all zones for {toon.getName()}."
    
class Teleport(MagicWord):
    aliases = ["tp", "goto"]
    desc = "Teleport to a specified zone."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("zoneName", str, False, '')]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.hood import ZoneUtil
        from toontown.toonbase import ToontownGlobals
        zoneName = args[0]

        # Can add stuff like streets to this too if you wanted, but if you do you'll want it to be a valid zone on that street. eg: 2100 is invalid, but any value 2101 to 2156 is fine.
        # so if you wanted to add a silly street key, theroetically you could do something like this: 'sillystreet': ToontownGlobals.SillyStreet +1,
        zoneName2Id = {'ttc': ToontownGlobals.ToontownCentral,
                       'dd': ToontownGlobals.DonaldsDock,
                       'dg': ToontownGlobals.DaisyGardens,
                       'mml': ToontownGlobals.MinniesMelodyland,
                       'tb': ToontownGlobals.TheBrrrgh,
                       'ddl': ToontownGlobals.DonaldsDreamland,
                       'gs': ToontownGlobals.GoofySpeedway,
                       'oz': ToontownGlobals.OutdoorZone,
                       'aa': ToontownGlobals.OutdoorZone,
                       'gz': ToontownGlobals.GolfZone,
                       'sbhq': ToontownGlobals.SellbotHQ,
                       'factory': ToontownGlobals.SellbotFactoryExt,
                       'cbhq': ToontownGlobals.CashbotHQ,
                       'lbhq': ToontownGlobals.LawbotHQ,
                       'bbhq': ToontownGlobals.BossbotHQ}
        
        try:
            zone = zoneName2Id[zoneName]
        except KeyError:
            return "Unknown zone name!"

        return f"Requested to teleport {toon.getName()} to zone {zone}.", toon.doId, [ZoneUtil.getBranchLoaderName(zone), ZoneUtil.getToonWhereName(zone), "", ZoneUtil.getHoodId(zone), zone, 0]

class ToggleSleep(MagicWord):
    aliases = ["sleep", "nosleep", "neversleep", "togglesleeping", "insomnia"]
    desc = "Toggles sleeping for the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.d_toggleSleep()
        return f"Toggled sleeping for {toon.getName()}."
    
class ToggleImmortal(MagicWord):
    aliases = ["immortal", "invincible", "invulnerable"]
    desc = "Toggle immortal mode. This makes the Toon immune to damage."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.setImmortalMode(not toon.immortalMode)
        return f"Toggled immortal mode for {toon.getName()}"
    
class ToggleGhost(MagicWord):
    aliases = ["ghost", "invisible", "spy"]
    desc = "Toggle ghost mode."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        # 1 is for the attic, 2 enables you to see yourself other ghost toons. 0 is off.
        toon.b_setGhostMode(2 if not toon.ghostMode else 0) # As it's primarily for moderation purposes, we set it to 2 here, or 0 if it's already on.
        return f"Toggled ghost mode for {toon.getName()}"
    
class SetGM(MagicWord):
    aliases = ["icon", "seticon", "gm", "gmicon", "setgmicon"]
    desc = "Sets the GM icon on the target."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("iconRequest", int, False, 0),]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.toonbase import TTLocalizer

        iconRequest = args[0]
        if iconRequest > len(TTLocalizer.GM_NAMES) or iconRequest < 0:
            return "Invalid GM icon ID!"
        
        toon.b_setGM(0) # Reset it first, otherwise the Toon keeps the old icon, but the name still changes.
        toon.b_setGM(iconRequest)
        return f"GM icon set to {iconRequest} for {toon.getName()}"
    
class SetMaxCarry(MagicWord):
    aliases = ["gagpouch", "pouch", "gagcapacity"]
    desc = "Set a Toon's gag pouch size."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("pouchSize", int, True)]

    def handleWord(self, invoker, avId, toon, *args):
        pouchSize = args[0]

        if pouchSize > 255 or pouchSize < 0:
            return "Specified pouch size must be between 1 and 255."

        toon.b_setMaxCarry(pouchSize)
        return f"Set gag pouch size to {pouchSize} for {toon.getName()}"
    
class ToggleInstantKill(MagicWord):
    aliases = ["instantkill", "instakill"]
    desc = "Toggle the ability to instantly kill a Cog with any gag."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER

    def handleWord(self, invoker, avId, toon, *args):
        toon.setInstantKillMode(not toon.instantKillMode)
        return f"Toggled instant-kill mode for {toon.getName()}"

class Fireworks(MagicWord):
    aliases = ["firework"]
    desc = "Starts a firework show."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("name", str, False, "newyear"), ("hood", str, False, "")]

    def handleWord(self, invoker, avId, toon, *args):
        name = args[0]
        hood = args[1]

        from toontown.toonbase import ToontownGlobals
        from toontown.parties import PartyGlobals
        name2showId = {
            'newyear': ToontownGlobals.NEWYEARS_FIREWORKS,
            'newyears': ToontownGlobals.NEWYEARS_FIREWORKS,
            'summer': ToontownGlobals.JULY4_FIREWORKS,
            'combo': ToontownGlobals.COMBO_FIREWORKS,
            'party': PartyGlobals.FireworkShows.Summer
        }

        if name not in name2showId:
            return f"Unknown firework name \"{name}\".  Valid names: {list(name2showId.keys())}"
        showId = name2showId[name]

        zoneToStyleDict = {
        ToontownGlobals.DonaldsDock : 5,
        ToontownGlobals.ToontownCentral : 0,
        ToontownGlobals.TheBrrrgh : 4,
        ToontownGlobals.MinniesMelodyland : 3,
        ToontownGlobals.DaisyGardens : 1,
        ToontownGlobals.OutdoorZone : 0,
        ToontownGlobals.GoofySpeedway : 0,
        ToontownGlobals.DonaldsDreamland : 2
        }
        
        from toontown.hood import ZoneUtil
        zones = []
        if not hood:
            zones = (toon.zoneId,)
        elif hood == "all":
            zones = zoneToStyleDict.keys()
        elif hood == "estate":
            if not toon.getHouseId():
                return "{} has no house.".format(toon.getName())
            world = _residentWorld(self.air, toon)
            if world is None:
                return "{} is not standing in their own live estate.".format(toon.getName())
            zones = (world.zoneId,)
        else:
            return "Missing hood argument."
        
        # Start our firework shows.  The manager owns the registry and is
        # what the shows report back to when they are done.
        count = 0
        for zone in zones:
            if self.air.fireworkMgr.startShow(zone, showId, zoneToStyleDict.get(zone, 0)):
                count += 1

        return f"Started firework {'show' if count == 1 else 'shows'} in {count} {'zone' if count == 1 else 'zones'}!"


class FireworksCannon(MagicWord):
    desc = ("Drops or removes the invoker's estate fireworks cannon -- the "
            "permanent prop EstateWorldOperation.__populate already "
            "generates for every estate, not a rental.  '~fireworkscannon' "
            "or '~fireworkscannon drop' (re)drops it if it is missing; "
            "'~fireworkscannon remove' takes it away.  Both are idempotent: "
            "dropping an already-dropped cannon or removing an "
            "already-removed one does nothing.")
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("command", str, False, 'drop')]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.estate.EstateWorld import makeFireworksCannon

        command = (args[0] if len(args) > 0 else '') or 'drop'
        command = str(command).strip().lower()
        if command not in ('drop', 'remove'):
            return "Specify drop or remove."

        if not toon.getHouseId():
            return "{} has no house.".format(toon.getName())

        world = _residentWorld(self.air, toon)
        if world is None:
            return "{} is not standing in their own live estate.".format(toon.getName())

        if command == 'remove':
            if world.fireworksCannon is not None:
                world.fireworksCannon.requestDelete()
                world.fireworksCannon = None
            return "Removed {}'s estate fireworks cannon.".format(toon.getName())

        if world.fireworksCannon is None:
            world.fireworksCannon = makeFireworksCannon(self.air, world)
        return "Dropped a fireworks cannon in {}'s estate.".format(toon.getName())


class Pond(MagicWord):
    desc = ("Regenerates or removes the invoker's estate fishing pond --  "
            "the permanent pond, spots and targets EstateWorldOperation."
            "__populate already generates for every estate. '~pond' or "
            "'~pond drop' (re)drops it if it is missing; '~pond remove' "
            "takes it away along with its spots and targets. Both are "
            "idempotent, the same shape as '~fireworkscannon'.")
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("command", str, False, 'drop')]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.estate.EstateWorld import makeFishingPond, teardownFishingPond

        command = (args[0] if len(args) > 0 else '') or 'drop'
        command = str(command).strip().lower()
        if command not in ('drop', 'remove'):
            return "Specify drop or remove."

        if not toon.getHouseId():
            return "{} has no house.".format(toon.getName())

        world = _residentWorld(self.air, toon)
        if world is None:
            return "{} is not standing in their own live estate.".format(toon.getName())

        if command == 'remove':
            teardownFishingPond(world)
            return "Removed {}'s estate fishing pond.".format(toon.getName())

        if world.fishingPond is None:
            makeFishingPond(self.air, world)
        return "Dropped a fishing pond in {}'s estate.".format(toon.getName())


class Rod(MagicWord):
    desc = "Sets the target's fishing rod, 0..FishGlobals.MaxRodId."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    accessLevel = 'ADMIN'
    arguments = [("rodId", int, False, 0)]

    def handleWord(self, invoker, avId, toon, *args):
        from toontown.fishing import FishGlobals

        rodId = args[0]
        if not 0 <= rodId <= FishGlobals.MaxRodId:
            return "Specify a rod id between 0 and {}.".format(FishGlobals.MaxRodId)

        toon.b_setFishingRod(rodId)
        return "Set {}'s fishing rod to {}.".format(toon.getName(), rodId)


class SetSpeedChatStyle(MagicWord):
    # The first version of this word did `from toontown.shtiker.OptionsPage
    # import speedChatStyles` to bounds-check/name the index -- OptionsPage.py is
    # a CLIENT Shticker Book page module; its class bodies default-
    # construct against `aspect2d` (`OptionsPage.py:124,469`
    # `def __init__(self, parent = aspect2d)`), a ShowBase builtin that
    # only exists in the client process's global namespace. Evaluating
    # that default at import time on the AI (no ShowBase, no `aspect2d`/
    # `render` builtins) raised `NameError: name 'render' is not
    # defined` inside DirectGui's own import chain and took the AI
    # process down. `toontown/toon/DistributedToonAI.py:2382-2391`'s
    # `b_setSpeedChatStyleIndex`/`setSpeedChatStyleIndex` -- the ACTUAL
    # AI-side pair this word calls -- do not import that module either,
    # for the same reason: no client-only import, ever, in AI-side code.
    # This version instead transcribes just the two AI-safe facts that
    # module's `speedChatStyles` tuple provides (`OptionsPage.py:13-52`):
    # its length (10, `_NUM_STYLES` below) and each entry's human name
    # (`OTPLocalizerEnglish.py:1165-1174`'s `SpeedChatStaticText`
    # 2000-2009, the `nameKey` field of each tuple) -- literal data, not
    # a live import, the same "copy the numbers, don't import the GUI
    # module" choice `godot/game/speed_chat_styles.gd`'s own
    # `SpeedChatStyles.STYLES` already made on the Godot side.
    #
    # Added for the Godot port's parity work (docs/UI_AND_CHAT.md
    # speed_chat_panel.gd SpeedChat-style-colour round): no existing
    # Magic Word could set this DB field, so there was no way to capture
    # a reference screenshot of a non-default SpeedChat colour scheme to
    # verify the port against.
    aliases = ["scstyle", "speedchatstyle"]
    desc = "Sets the target's SpeedChat colour style (Options page swatch index)."
    advancedDesc = "This Magic Word sets the target's speedChatStyleIndex DB field, the same one the Shticker " \
                   "Book's Options page 'SpeedChat Style' arrows cycle through " \
                   "(toontown/shtiker/OptionsPage.py's speedChatStyles table, index 0-9: Purple, Blue, Cyan, " \
                   "Teal, Green, Yellow, Orange, Red, Pink, Brown). Changes the SpeedChat menu's own frame/arrow " \
                   "colour AND the target's SpeedChat/quicktalk nametag balloon colour immediately."
    execLocation = MagicWordConfig.EXEC_LOC_SERVER
    arguments = [("index", int, True)]

    # OptionsPage.py:13-52's speedChatStyles, AI-safe subset only (length
    # + name, no colour tuples/no import -- see the class doc above for
    # why this is transcribed rather than imported).
    _STYLE_NAMES = ["Purple", "Blue", "Cyan", "Teal", "Green", "Yellow", "Orange", "Red", "Pink", "Brown"]
    _NUM_STYLES = len(_STYLE_NAMES)

    def handleWord(self, invoker, avId, toon, *args):
        index = args[0]

        if not 0 <= index < self._NUM_STYLES:
            return "Can't set {}'s SpeedChat style to {}! Specify a value between 0 and {}.".format(
                toon.getName(), index, self._NUM_STYLES - 1)

        toon.b_setSpeedChatStyleIndex(index)
        return "{}'s SpeedChat style has been set to {} ({}).".format(
            toon.getName(), index, self._STYLE_NAMES[index])


# Instantiate all classes defined here to register them.
# A bit hacky, but better than the old system
for item in list(globals().values()):
    if isinstance(item, type) and issubclass(item, MagicWord):
        i = item()
