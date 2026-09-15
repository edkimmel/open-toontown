from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogFurnitureItem
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
