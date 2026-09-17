from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate.EstateProvisioner import EstateProvisioner
from toontown.estate.EstateWorld import EstatePetActivation, EstateWorld, EstateWorldOperation

class EstateManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('EstateManagerAI')

    # how long an estate with nobody in it stays up before it is unloaded
    ESTATE_IDLE_TIMEOUT = 30.0
    # how long to wait for a closed estate's delete before reopening anyway
    ESTATE_CLOSE_TIMEOUT = 10.0

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.estate = {}
        self.zoneId2owner = {}
        self.owner2estateZone = {}
        self.provisioner = EstateProvisioner(air)
        # accountId -> live EstateWorld, and the avatars waiting for one
        self.worlds = {}
        self.pendingWorlds = {}
        self.zoneId2world = {}
        # accountId -> the estate doId whose delete we are still waiting for
        self.closingWorlds = {}

    def getOwnerFromZone(self, zoneId):
        return self.zoneId2owner.get(zoneId)

    def getEstateZones(self, ownerId):
        zoneId = self.owner2estateZone.get(ownerId)
        if zoneId is None:
            return []
        return [zoneId]

    def getEstateHouseZones(self, ownerId):
        world = self.__worldForAvatar(ownerId)
        if world is None:
            return []
        return world.getHouseZones()

    def __worldForAvatar(self, avId):
        zoneId = self.owner2estateZone.get(avId)
        if zoneId is None:
            return None
        return self.zoneId2world.get(zoneId)

    def getEstateZone(self, avId, name):
        senderId = self.air.getAvatarIdFromSender()
        self.notify.debug('getEstateZone from %s for avId %s name %s' % (senderId, avId, name))
        if avId != senderId:
            # Visiting somebody else's estate is not supported yet.
            return

        sender = self.air.doId2do.get(senderId)
        if sender is None:
            self.notify.warning('Estate request from an unknown avatar %s!' % senderId)
            return

        accountId = sender.DISLid
        if not accountId:
            self.notify.warning('Avatar %s has no account!' % senderId)
            return

        world = self.worlds.get(accountId)
        if world is not None:
            # The estate is already up; the same zone is handed out again.
            self.__admit(world, senderId)
            return

        pending = self.pendingWorlds.get(accountId)
        if pending is not None:
            if senderId not in pending:
                pending.append(senderId)
                self.__watchAvatar(senderId)

            return

        self.pendingWorlds[accountId] = [senderId]
        self.__watchAvatar(senderId)
        if accountId in self.closingWorlds:
            # The previous visit is still being torn down; __worldClosed opens
            # the new one once the old objects are really gone.
            return

        self.__openWorld(accountId)

    def __openWorld(self, accountId):
        self.provisioner.provision(accountId, lambda estateId, houseIds:
                                   self.__handleEstateProvisioned(accountId, estateId, houseIds))

    def __handleEstateProvisioned(self, accountId, estateId, houseIds):
        if not estateId:
            self.notify.warning('Account %s has no estate to open!' % accountId)
            self.pendingWorlds.pop(accountId, None)
            return

        waiting = self.pendingWorlds.get(accountId) or []
        ownerId = waiting[0] if waiting else 0
        EstateWorldOperation(self, EstateWorld(accountId, ownerId, estateId, houseIds)).start()

    def worldReady(self, world):
        waiting = self.pendingWorlds.pop(world.accountId, [])
        if world.zoneId is None:
            self.notify.warning('Could not open the estate for account %s!' % world.accountId)
            return

        self.worlds[world.accountId] = world
        self.zoneId2world[world.zoneId] = world
        self.zoneId2owner[world.zoneId] = world.ownerId
        for avId in waiting:
            self.__admit(world, avId)

        if not world.occupants:
            # Everybody who asked for it left again while it was opening.
            self.__armIdleTimer(world)

    def __watchAvatar(self, avId):
        # toontown/building/DistributedBoardingPartyAI.py:70-71 watches an
        # avatar the same way: the delete event for a disconnect, the logical
        # zone change for a walk-out.
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.removeFromEstate,
                        extraArgs=[avId])
        self.accept(self.staticGetLogicalZoneChangeEvent(avId),
                    self.__handleZoneChange, extraArgs=[avId])

    def __ignoreAvatar(self, avId):
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.ignore(self.staticGetLogicalZoneChangeEvent(avId))

    def __handleZoneChange(self, avId, zoneId, oldZoneId):
        world = self.__worldForAvatar(avId)
        if world is not None and zoneId in world.getZones():
            # The estate zone and the house interiors are all one visit.
            return

        self.removeFromEstate(avId)

    def __admit(self, world, avId):
        self.__cancelIdleTimer(world.accountId)
        world.addOccupant(avId)
        self.__watchAvatar(avId)
        self.estate[avId] = world.estate
        self.owner2estateZone[avId] = world.zoneId
        self.sendUpdateToAvatarId(avId, 'setAvHouseId', [avId, world.houseIds])
        self.sendUpdateToAvatarId(avId, 'setEstateZone', [world.ownerId, world.zoneId])
        # DistributedToonAI.enterEstate:3057-3072 is what gives the avatar its
        # collision sphere and enters it into the pet looker system, the half
        # a pet's awareness code notices (toontown/pets/PetLookerAI.py); it
        # reads the zone lookups above, so it runs after them.  Both it and
        # exitEstate only exist when pets are on.
        av = self.air.doId2do.get(avId)
        if av is not None and hasattr(av, 'enterEstate') and not av.isInEstate():
            av.enterEstate(world.ownerId, world.zoneId)
        # ``EstateWorldOperation.__activatePets`` only sees the avatars that
        # were waiting while a world first opened.  A visitor admitted after
        # worldReady still owns a persistent pet row, so use the same DBSS
        # activation/wait/placement helper here.  It deduplicates both an
        # already-placed pet and an activation still waiting for ENTER_AI.
        EstatePetActivation(self.air, world, [avId]).start()

    def exitEstate(self):
        senderId = self.air.getAvatarIdFromSender()
        self.notify.debug('exitEstate from %s' % senderId)
        self.removeFromEstate(senderId)

    def removeFromEstate(self, avId):
        self.__ignoreAvatar(avId)
        self.estate.pop(avId, None)
        av = self.air.doId2do.get(avId)
        if av is not None and hasattr(av, 'exitEstate') and av.isInEstate():
            # the other half of __admit's enterEstate: the collision sphere
            # and the looker go away with the visit.  DistributedToonAI.delete
            # (:289-291) does the same for an avatar that disconnects, and
            # exitEstate cannot run twice -- isInEstate is the flag it clears.
            av.exitEstate()
        for waiting in self.pendingWorlds.values():
            if avId in waiting:
                waiting.remove(avId)

        zoneId = self.owner2estateZone.pop(avId, None)
        if zoneId is None:
            return

        world = self.zoneId2world.get(zoneId)
        if world is None:
            return

        world.removeOccupant(avId)
        if world.occupants:
            return

        # An estate is not torn down the moment it empties: a toon who walks
        # out of the estate zone and straight back in is the common case, and
        # reopening costs a database read per house.
        self.__armIdleTimer(world)

    def __idleTaskName(self, accountId):
        return 'estate-idle-%s' % accountId

    def __armIdleTimer(self, world):
        taskMgr.remove(self.__idleTaskName(world.accountId))
        taskMgr.doMethodLater(self.ESTATE_IDLE_TIMEOUT, self.__idleTimedOut,
                              self.__idleTaskName(world.accountId),
                              extraArgs=[world.accountId])

    def __cancelIdleTimer(self, accountId):
        taskMgr.remove(self.__idleTaskName(accountId))

    def __idleTimedOut(self, accountId):
        world = self.worlds.get(accountId)
        if world is None or world.occupants:
            # Somebody was admitted again while the timer was running.
            return

        self.__closeWorld(world)

    def __closeWorld(self, world):
        self.__cancelIdleTimer(world.accountId)
        for avId in list(world.occupants):
            self.__ignoreAvatar(avId)
            self.estate.pop(avId, None)
            self.owner2estateZone.pop(avId, None)
            world.removeOccupant(avId)

        self.worlds.pop(world.accountId, None)
        self.zoneId2world.pop(world.zoneId, None)
        self.zoneId2owner.pop(world.zoneId, None)
        world.destroy(self.air)
        # The estate and the houses are database objects: requestDelete only
        # unloads the State Server's copy (STATESERVER_OBJECT_DELETE_RAM,
        # direct/distributed/AstronInternalRepository.py:572-584), the record
        # stays and a later sendActivate brings the same doId back with its
        # fields.  The object leaves air.doId2do only when that delete comes
        # back (handleObjExit, :301-313), so the account stays closed until
        # then and the next activation cannot pick up the old object.
        accountId = world.accountId
        self.closingWorlds[accountId] = world.estateId
        self.acceptOnce('distObjDelete-%s' % world.estateId, self.__worldClosed,
                        extraArgs=[accountId])
        taskMgr.doMethodLater(self.ESTATE_CLOSE_TIMEOUT, self.__closeTimedOut,
                              self.__closeTaskName(accountId), extraArgs=[accountId])

    def __closeTaskName(self, accountId):
        return 'estate-close-%s' % accountId

    def __closeTimedOut(self, accountId):
        self.notify.warning('Estate %s never came back deleted; reopening anyway.'
                            % self.closingWorlds.get(accountId))
        self.__worldClosed(accountId)

    def __worldClosed(self, accountId):
        estateId = self.closingWorlds.pop(accountId, None)
        if estateId is None:
            return

        self.ignore('distObjDelete-%s' % estateId)
        taskMgr.remove(self.__closeTaskName(accountId))
        if self.pendingWorlds.get(accountId):
            self.__openWorld(accountId)
