from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate.EstateProvisioner import EstateProvisioner
from toontown.estate.EstateWorld import EstateWorld, EstateWorldOperation

class EstateManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('EstateManagerAI')

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
            self.__closeWorld(world)

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
        world.addOccupant(avId)
        self.__watchAvatar(avId)
        self.estate[avId] = world.estate
        self.owner2estateZone[avId] = world.zoneId
        self.sendUpdateToAvatarId(avId, 'setAvHouseId', [avId, world.houseIds])
        self.sendUpdateToAvatarId(avId, 'setEstateZone', [world.ownerId, world.zoneId])

    def exitEstate(self):
        senderId = self.air.getAvatarIdFromSender()
        self.notify.debug('exitEstate from %s' % senderId)
        self.removeFromEstate(senderId)

    def removeFromEstate(self, avId):
        self.__ignoreAvatar(avId)
        self.estate.pop(avId, None)
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

        self.__closeWorld(world)

    def __closeWorld(self, world):
        for avId in list(world.occupants):
            self.__ignoreAvatar(avId)
            self.estate.pop(avId, None)
            self.owner2estateZone.pop(avId, None)
            world.removeOccupant(avId)

        self.worlds.pop(world.accountId, None)
        self.zoneId2world.pop(world.zoneId, None)
        self.zoneId2owner.pop(world.zoneId, None)
        world.destroy(self.air)
