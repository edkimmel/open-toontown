from toontown.toonbase import ToontownGlobals
from direct.distributed.ClockDelta import *
from direct.task import Task
from toontown.minigame import CannonGameGlobals
from direct.distributed import DistributedObjectAI
from . import CannonGlobals

class DistributedCannonAI(DistributedObjectAI.DistributedObjectAI):
    """The estate pinball cannon (dclass DistributedCannon,
    etc/toon.dc:993-1011): a single-occupant ride that fires the occupant at
    a DistributedTargetAI, whose doId is this object's required `targetId`.

    `setFired` (:1004) and `setCannonExit` (:1008) are declared but dead --
    no client sends the first and no client handles the second -- so neither
    has a handler here.

    The reference only released the session on `setLanded` and never sent a
    following CANNON_MOVIE_CLEAR, so the `broadcast ram` movie field kept
    replaying the terminal mode to anyone entering the zone afterwards, and
    a forced exit left `avId` set so the cannon could never be entered
    again; __release clears both the way DistributedClosetAI.__release does
    (DistributedClosetAI.py:234-251).  The reference also acted on
    `setCannonPosition`/`setCannonLit`/`setLanded` from any client in the
    zone, and trusted the sender's aim and bumper position; both are checked
    here against the occupant and against the ranges the client already
    clamps itself to (DistributedCannon.py:33-37).
    """

    notify = directNotify.newCategory('DistributedCannonAI')

    def __init__(self, air, estateId, targetId, x, y, z, h, p, r):
        DistributedObjectAI.DistributedObjectAI.__init__(self, air)
        self.posHpr = [x,
         y,
         z,
         h,
         p,
         r]
        self.avId = 0
        self.active = 1
        self.estateId = estateId
        self.timeoutTask = None
        self.targetId = targetId
        self.cannonBumperPos = list(ToontownGlobals.PinballCannonBumperInitialPos)
        return

    def delete(self):
        self.ignoreAll()
        self.__stopTimeout()
        DistributedObjectAI.DistributedObjectAI.delete(self)

    def requestEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if self.avId == 0:
            self.avId = avId
            self.__stopTimeout()
            self.setMovie(CannonGlobals.CANNON_MOVIE_LOAD, self.avId)
            self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__handleUnexpectedExit, extraArgs=[avId])
            self.acceptOnce('bootAvFromEstate-' + str(avId), self.__handleBootMessage, extraArgs=[avId])
            self.__startTimeout(CannonGlobals.CANNON_TIMEOUT)
        else:
            self.air.writeServerEvent('suspicious', avId, 'DistributedCannonAI.requestEnter cannon already occupied')
            self.notify.warning('requestEnter() - cannon already occupied')
            self.sendUpdateToAvatarId(avId, 'requestExit', [])

    def setMovie(self, mode, avId):
        self.avId = avId
        self.sendUpdate('setMovie', [mode, avId])

    def getCannonBumperPos(self):
        self.notify.debug('---------getCannonBumperPos %s' % self.cannonBumperPos)
        return self.cannonBumperPos

    def requestBumperMove(self, x, y, z):
        avId = self.air.getAvatarIdFromSender()
        pos = [self.__clampBumper(value, initial, avId)
               for value, initial in zip((x, y, z), ToontownGlobals.PinballCannonBumperInitialPos)]
        self.cannonBumperPos = pos
        self.sendUpdate('setCannonBumperPos', pos)

    def getPosHpr(self):
        return self.posHpr

    def getEstateId(self):
        return self.estateId

    def getTargetId(self):
        return self.targetId

    def setCannonPosition(self, zRot, angle):
        avId = self.air.getAvatarIdFromSender()
        if not self.__isOccupant(avId, 'setCannonPosition'):
            return
        self.notify.debug('setCannonPosition: ' + str(avId) + ': zRot=' + str(zRot) + ', angle=' + str(angle))
        zRot, angle = self.__clampAim(zRot, angle, avId)
        self.sendUpdate('updateCannonPosition', [avId, zRot, angle])

    def setCannonLit(self, zRot, angle):
        avId = self.air.getAvatarIdFromSender()
        if not self.__isOccupant(avId, 'setCannonLit'):
            return
        self.__stopTimeout()
        self.notify.debug('setCannonLit: ' + str(avId) + ': zRot=' + str(zRot) + ', angle=' + str(angle))
        zRot, angle = self.__clampAim(zRot, angle, avId)
        fireTime = CannonGameGlobals.FUSE_TIME
        self.sendUpdate('setCannonWillFire', [avId,
         fireTime,
         zRot,
         angle,
         globalClockDelta.getRealNetworkTime()])

    def setLanded(self):
        avId = self.air.getAvatarIdFromSender()
        if not self.__isOccupant(avId, 'setLanded'):
            return
        self.__release(CannonGlobals.CANNON_MOVIE_LANDED, 0)

    def forceExit(self):
        """Boot whoever is riding, if anyone -- what a rental's expiry needs
        before requestDelete pulls the cannon out from under an occupant
        (DistributedEstateAI._rentalTeardown).  Same FORCE_EXIT/CLEAR pair a
        timeout or a disconnect already sends; a no-op if the cannon is
        empty."""
        if self.avId:
            self.__doExit()

    def setActive(self, active):
        if active < 0 or active > 1:
            self.air.writeServerEvent('suspicious', active, 'DistributedCannon.setActive value should be 0-1 range')
            return
        self.active = active
        self.sendUpdate('setActiveState', [active])

    def __isOccupant(self, avId, methodName):
        if avId != 0 and avId == self.avId:
            return True
        self.air.writeServerEvent('suspicious', avId,
                                  'DistributedCannonAI.%s from a non-occupant' % methodName)
        return False

    def __clampAim(self, zRot, angle, avId):
        clamped = (min(max(zRot, CannonGlobals.CANNON_ROTATION_MIN), CannonGlobals.CANNON_ROTATION_MAX),
                   min(max(angle, CannonGlobals.CANNON_ANGLE_MIN), CannonGlobals.CANNON_ANGLE_MAX))
        if clamped != (zRot, angle):
            self.air.writeServerEvent('suspicious', avId,
                                      'DistributedCannonAI aim out of range')
        return clamped

    def __clampBumper(self, value, initial, avId):
        limit = CannonGlobals.CANNON_BUMPER_MOVE_LIMIT
        clamped = min(max(value, initial - limit), initial + limit)
        if clamped != value:
            self.air.writeServerEvent('suspicious', avId,
                                      'DistributedCannonAI.requestBumperMove out of range')
        return clamped

    def __startTimeout(self, timeLimit):
        self.__stopTimeout()
        self.timeoutTask = taskMgr.doMethodLater(timeLimit, self.__handleTimeout, self.taskName('timeout'))

    def __stopTimeout(self):
        if self.timeoutTask != None:
            taskMgr.remove(self.timeoutTask)
            self.timeoutTask = None
        return

    def __handleTimeout(self, task):
        self.notify.debug('Timeout expired!')
        self.__doExit()
        return Task.done

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar:' + str(avId) + ' has exited unexpectedly')
        self.__doExit()

    def __handleBootMessage(self, avId):
        self.notify.warning('avatar:' + str(avId) + ' got booted ')
        self.__doExit()

    def __doExit(self):
        self.__release(CannonGlobals.CANNON_MOVIE_FORCE_EXIT, self.avId)

    def __release(self, mode, movieAvId):
        avId = self.avId
        self.__stopTimeout()
        if avId:
            self.ignore(self.air.getAvatarExitEvent(avId))
            self.ignore('bootAvFromEstate-' + str(avId))
        self.setMovie(mode, movieAvId)
        self.setMovie(CannonGlobals.CANNON_MOVIE_CLEAR, 0)
