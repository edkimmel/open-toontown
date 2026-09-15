from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogFurnitureItem
from toontown.catalog import CatalogItem
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.estate.DistributedPhoneAI import DistributedPhoneAI

# every house has a telephone, and it cannot be put away
# (toontown/estate/houseDesign.py:1546)
PhoneFurnitureType = 1399


class DistributedFurnitureManagerAI(DistributedObjectAI):
    """Director lock and furniture-mode session for one house's furniture.

    Guest-edit policy: any avatar standing in the house may hold the
    director lock (the client already renders a non-owner director,
    houseDesign.py's fDirector=0 branch), but only the owner's mutating
    requests are honoured once the attic/room RPCs are implemented -- the
    same split the client already assumes when it refuses to let a guest
    delete an item (houseDesign.py's ownerId check before a delete).
    Holding the lock and being allowed to mutate are therefore two
    separate checks; this class only grants/releases the lock.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureManagerAI')

    def __init__(self, air, house, interior):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.interior = interior
        self.items = []
        self.directorAvId = 0
        self.watchingAvIds = set()

    def getOwnerId(self):
        return self.house.getAvatarId()

    def getOwnerName(self):
        return self.house.getName()

    def getInteriorId(self):
        return self.interior.doId

    def getAtticItems(self):
        return self.house.getAtticItems()

    def getAtticWallpaper(self):
        return self.house.getAtticWallpaper()

    def getAtticWindows(self):
        return self.house.getAtticWindows()

    def getDeletedItems(self):
        return self.house.getDeletedItems()

    def d_setAtticItems(self, blob):
        self.sendUpdate('setAtticItems', [blob])

    def b_setAtticItems(self, blob):
        self.house.setAtticItems(blob)
        self.d_setAtticItems(blob)

    def d_setDeletedItems(self, blob):
        self.sendUpdate('setDeletedItems', [blob])

    def b_setDeletedItems(self, blob):
        self.house.setDeletedItems(blob)
        self.d_setDeletedItems(blob)

    def getDirector(self):
        return self.directorAvId

    def setDirector(self, avId):
        self.directorAvId = avId

    def d_setDirector(self, avId):
        self.sendUpdate('setDirector', [avId])

    def b_setDirector(self, avId):
        self.setDirector(avId)
        self.d_setDirector(avId)

    def suggestDirector(self, avId):
        senderId = self.air.getAvatarIdFromSender()
        if avId != 0 and avId != senderId:
            self.air.writeServerEvent(
                'suspicious', senderId,
                'DistributedFurnitureManagerAI.suggestDirector for another avatar %s' % avId)
            return
        if avId == 0:
            if self.directorAvId == senderId:
                self.__releaseDirector()
            return
        if self.directorAvId != 0:
            # someone else already directs; the request is not honoured
            return
        self.__grantDirector(senderId)

    def __grantDirector(self, avId):
        self.directorAvId = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleDirectorExit, extraArgs=[avId])
        self.d_setDirector(avId)

    def __releaseDirector(self):
        self.ignore(self.air.getAvatarExitEvent(self.directorAvId))
        self.directorAvId = 0
        self.d_setDirector(0)

    def __handleDirectorExit(self, avId):
        if self.directorAvId != avId:
            return
        self.directorAvId = 0
        self.d_setDirector(0)

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.watchingAvIds:
            return
        self.watchingAvIds.add(avId)
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleWatcherExit, extraArgs=[avId])

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        self.__stopWatching(avId)

    def __handleWatcherExit(self, avId):
        self.__stopWatching(avId)

    def __stopWatching(self, avId):
        if avId not in self.watchingAvIds:
            return
        self.watchingAvIds.discard(avId)
        self.ignore(self.air.getAvatarExitEvent(avId))

    def __mayMutate(self, avId):
        return avId != 0 and avId == self.directorAvId and avId == self.getOwnerId()

    def __reindexAfterRemoval(self, removedIndex):
        for distObj in self.items:
            if distObj.interiorIndex is not None and distObj.interiorIndex > removedIndex:
                distObj.interiorIndex -= 1

    def __removeFromInterior(self, interiorIndex):
        items = self.house.getInteriorItemList()
        if interiorIndex is None or interiorIndex >= len(items):
            return
        del items[interiorIndex]
        self.house.setInteriorItemList(items)
        self.__reindexAfterRemoval(interiorIndex)

    def __findItem(self, doId):
        distObj = self.air.doId2do.get(doId)
        if distObj is None or distObj not in self.items:
            return None
        return distObj

    def moveItemToAtticMessage(self, doId, context):
        avId = self.air.getAvatarIdFromSender()
        retcode = -1
        if self.__mayMutate(avId):
            distObj = self.__findItem(doId)
            if distObj is not None and distObj.item.isDeletable():
                self.__removeFromInterior(distObj.interiorIndex)
                attic = self.house.getAtticItemList()
                attic.append(distObj.item)
                self.b_setAtticItems(attic.getBlob())
                self.items.remove(distObj)
                distObj.requestDelete()
                retcode = 0
        self.sendUpdateToAvatarId(avId, 'moveItemToAtticResponse', [retcode, context])

    def moveItemFromAtticMessage(self, index, x, y, z, h, p, r, context):
        avId = self.air.getAvatarIdFromSender()
        retcode = -1
        objectId = 0
        if self.__mayMutate(avId):
            attic = self.house.getAtticItemList()
            if index < len(attic):
                item = attic.pop(index)
                self.b_setAtticItems(attic.getBlob())
                item.posHpr = (x, y, z, h, p, r)
                interior = self.house.getInteriorItemList()
                interiorIndex = len(interior)
                interior.append(item)
                self.house.setInteriorItemList(interior)
                distObj = DistributedFurnitureItemAI(self.air, self, item,
                                                     interiorIndex=interiorIndex)
                distObj.generateWithRequired(self.zoneId)
                self.items.append(distObj)
                objectId = distObj.doId
                retcode = 0
        self.sendUpdateToAvatarId(avId, 'moveItemFromAtticResponse',
                                  [retcode, objectId, context])

    def deleteItemFromAtticMessage(self, blob, index, context):
        avId = self.air.getAvatarIdFromSender()
        retcode = -1
        if self.__mayMutate(avId):
            attic = self.house.getAtticItemList()
            offered = CatalogItem.getItem(bytes(blob), store=CatalogItem.Customization)
            if index < len(attic) and attic[index] == offered:
                removed = attic.pop(index)
                self.b_setAtticItems(attic.getBlob())
                deleted = self.house.getDeletedItemList()
                deleted.append(removed)
                self.b_setDeletedItems(deleted.getBlob())
                retcode = 0
        self.sendUpdateToAvatarId(avId, 'deleteItemFromAtticResponse', [retcode, context])

    def deleteItemFromRoomMessage(self, blob, doId, context):
        avId = self.air.getAvatarIdFromSender()
        retcode = -1
        if self.__mayMutate(avId):
            distObj = self.__findItem(doId)
            offered = CatalogItem.getItem(bytes(blob), store=CatalogItem.Customization)
            if (distObj is not None and distObj.item == offered and
                    distObj.item.isDeletable()):
                self.__removeFromInterior(distObj.interiorIndex)
                deleted = self.house.getDeletedItemList()
                deleted.append(distObj.item)
                self.b_setDeletedItems(deleted.getBlob())
                self.items.remove(distObj)
                distObj.requestDelete()
                retcode = 0
        self.sendUpdateToAvatarId(avId, 'deleteItemFromRoomResponse', [retcode, context])

    def recoverDeletedItemMessage(self, blob, index, context):
        avId = self.air.getAvatarIdFromSender()
        retcode = -1
        if self.__mayMutate(avId):
            deleted = self.house.getDeletedItemList()
            offered = CatalogItem.getItem(bytes(blob), store=CatalogItem.Customization)
            if index < len(deleted) and deleted[index] == offered:
                removed = deleted.pop(index)
                self.b_setDeletedItems(deleted.getBlob())
                attic = self.house.getAtticItemList()
                attic.append(removed)
                self.b_setAtticItems(attic.getBlob())
                retcode = 0
        self.sendUpdateToAvatarId(avId, 'recoverDeletedItemResponse', [retcode, context])

    def createFurniture(self, zoneId):
        """Generate a distributed object for each item standing in the room.
        The items reparent themselves to the interior through this manager
        (toontown/estate/DistributedFurnitureItem.py:56-61), so the manager
        and the interior must already exist."""
        hasPhone = False
        for item in self.house.getInteriorItemList():
            if self.__isPhone(item):
                hasPhone = True
            self.__generateItem(item, zoneId)

        if not hasPhone:
            self.__generateItem(
                CatalogFurnitureItem.CatalogFurnitureItem(PhoneFurnitureType),
                zoneId)

    def destroy(self):
        for item in self.items:
            item.requestDelete()

        self.items = []
        self.ignoreAll()
        self.watchingAvIds = set()
        self.directorAvId = 0
        self.requestDelete()

    def __isPhone(self, item):
        return (isinstance(item, CatalogFurnitureItem.CatalogFurnitureItem) and
                item.getFlags() & CatalogFurnitureItem.FLPhone)

    def __generateItem(self, item, zoneId):
        if self.__isPhone(item):
            distObj = DistributedPhoneAI(self.air, self, item)
        else:
            # the rest of the furniture is not interactive yet
            return None
        distObj.generateWithRequired(zoneId)
        self.items.append(distObj)
        return distObj
