from panda3d.core import *
from direct.distributed import DistributedObject
from direct.directnotify import DirectNotifyGlobal
from otp.otpbase import OTPGlobals
from toontown.pets import PetHandle

class FriendManager(DistributedObject.DistributedObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('FriendManager')
    neverDisable = 1

    def __init__(self, cr):
        DistributedObject.DistributedObject.__init__(self, cr)
        self.__available = 0
        self.gameSpecificFunction = None
        # petId -> callbacks.  A response is a snapshot of one pet, never a
        # generic "current pet" reply: setPetId can change while its DB read
        # is in flight.
        self.__petDetailsCallbacks = {}
        self.__petDetailsContext = None
        self.__petDetailsPetId = 0
        self.__nextPetDetailsContext = 1
        return

    def setAvailable(self, available):
        self.__available = available
        if self.__available and self.gameSpecificFunction:
            self.gameSpecificFunction()

    def getAvailable(self):
        return self.__available

    def setGameSpecificFunction(self, function):
        self.gameSpecificFunction = function

    def executeGameSpecificFunction(self):
        if self.__available and self.gameSpecificFunction:
            self.gameSpecificFunction()

    def generate(self):
        if base.cr.friendManager != None:
            base.cr.friendManager.delete()
        base.cr.friendManager = self
        DistributedObject.DistributedObject.generate(self)
        return

    def disable(self):
        self.__finishPetDetails(None)
        base.cr.friendManager = None
        DistributedObject.DistributedObject.disable(self)
        return

    def delete(self):
        self.gameSpecificFunction = None
        self.__finishPetDetails(None)
        base.cr.friendManager = None
        DistributedObject.DistributedObject.delete(self)
        return

    def up_friendQuery(self, inviteeId):
        self.sendUpdate('friendQuery', [inviteeId])
        self.notify.debug('Client: friendQuery(%d)' % inviteeId)

    def up_cancelFriendQuery(self, context):
        self.sendUpdate('cancelFriendQuery', [context])
        self.notify.debug('Client: cancelFriendQuery(%d)' % context)

    def up_inviteeFriendConsidering(self, yesNo, context):
        self.sendUpdate('inviteeFriendConsidering', [yesNo, context])
        self.notify.debug('Client: inviteeFriendConsidering(%d, %d)' % (yesNo, context))

    def up_inviteeFriendResponse(self, yesNoMaybe, context):
        self.sendUpdate('inviteeFriendResponse', [yesNoMaybe, context])
        self.notify.debug('Client: inviteeFriendResponse(%d, %d)' % (yesNoMaybe, context))

    def up_inviteeAcknowledgeCancel(self, context):
        self.sendUpdate('inviteeAcknowledgeCancel', [context])
        self.notify.debug('Client: inviteeAcknowledgeCancel(%d)' % context)

    def friendConsidering(self, yesNoAlready, context):
        self.notify.info('Roger Client: friendConsidering(%d, %d)' % (yesNoAlready, context))
        messenger.send('friendConsidering', [yesNoAlready, context])

    def friendResponse(self, yesNoMaybe, context):
        self.notify.debug('Client: friendResponse(%d, %d)' % (yesNoMaybe, context))
        messenger.send('friendResponse', [yesNoMaybe, context])

    def inviteeFriendQuery(self, inviterId, inviterName, inviterDna, context):
        self.notify.debug('Client: inviteeFriendQuery(%d, %s, dna, %d)' % (inviterId, inviterName, context))
        if not hasattr(base, 'localAvatar'):
            self.up_inviteeFriendConsidering(0, context)
            return
        if inviterId in base.localAvatar.ignoreList:
            self.up_inviteeFriendConsidering(4, context)
            return
        if not base.localAvatar.acceptingNewFriends:
            self.up_inviteeFriendConsidering(6, context)
            return
        self.up_inviteeFriendConsidering(self.__available, context)
        if self.__available:
            messenger.send('friendInvitation', [inviterId,
             inviterName,
             inviterDna,
             context])

    def inviteeCancelFriendQuery(self, context):
        self.notify.debug('Client: inviteeCancelFriendQuery(%d)' % context)
        messenger.send('cancelFriendInvitation', [context])
        self.up_inviteeAcknowledgeCancel(context)

    def up_requestSecret(self):
        self.notify.warning('Sending Request')
        self.sendUpdate('requestSecret', [])

    def requestSecretResponse(self, result, secret):
        messenger.send('requestSecretResponse', [result, secret])

    def up_submitSecret(self, secret):
        self.sendUpdate('submitSecret', [secret])

    def submitSecretResponse(self, result, avId):
        messenger.send('submitSecretResponse', [result, avId])

    def up_getFriendsListRequest(self):
        self.sendUpdate('getFriendsListRequest', [])

    def getFriendsListResponse(self, errorCode, friendDetails):
        self.notify.debug('Client: getFriendsListResponse(%d, %d)' % (errorCode, len(friendDetails)))
        base.cr.handleGetFriendsListResponse(errorCode, friendDetails)

    def requestOwnPetDetails(self, callback):
        petId = self.__getLocalPetId()
        if not petId:
            callback(None)
            return
        # Coalesce only equal identity snapshots.  A P -> Q switch waits for
        # the P reply, then starts Q; it must never hand P to Q's callbacks.
        self.__petDetailsCallbacks.setdefault(petId, []).append(callback)
        if self.__petDetailsContext is not None:
            return
        self.__startPetDetails(petId)

    def __getLocalPetId(self):
        if not hasattr(base, 'localAvatar'):
            return 0
        return base.localAvatar.getPetId()

    def __startPetDetails(self, petId):
        if not petId or petId != self.__getLocalPetId():
            return
        context = self.__nextPetDetailsContext
        self.__nextPetDetailsContext = (context + 1) & 4294967295
        if self.__nextPetDetailsContext == 0:
            self.__nextPetDetailsContext = 1
        self.__petDetailsContext = context
        self.__petDetailsPetId = petId
        self.sendUpdate('requestOwnPetDetails', [context])

    def ownPetDetailsResponse(self, context, result, petId, details):
        if context != self.__petDetailsContext:
            self.notify.warning('Ignoring stale pet-details response %s' % context)
            return
        requestedPetId = self.__petDetailsPetId
        callbacks = self.__petDetailsCallbacks.pop(requestedPetId, [])
        self.__petDetailsContext = None
        self.__petDetailsPetId = 0
        avatar = None
        currentPetId = self.__getLocalPetId()
        if result and details and requestedPetId == currentPetId:
            try:
                candidate = PetHandle.PetDetailsAvatar(base.cr, petId, details)
                if (candidate.doId == requestedPetId and
                        candidate.ownerId == base.localAvatar.getDoId()):
                    avatar = candidate
                else:
                    self.notify.warning('Ignoring mismatched own-pet response %s' % context)
            except (IndexError, TypeError, ValueError):
                self.notify.warning('Ignoring invalid own-pet response %s' % context)
        # Q may have become R while P was in flight.  Retain only callbacks
        # for the one pet that is current *at completion*; every other bucket
        # is a stale identity request and must resolve exactly once.
        staleCallbacks = []
        for queuedPetId in list(self.__petDetailsCallbacks):
            if queuedPetId != currentPetId:
                staleCallbacks.extend(self.__petDetailsCallbacks.pop(queuedPetId))
        for callback in callbacks:
            callback(avatar)
        for callback in staleCallbacks:
            callback(None)
        # A different pet was requested while P was outstanding.  Advance
        # only after P's callbacks have been safely failed/completed.  With
        # no current pet, all buckets were drained and no request is active.
        currentPetId = self.__getLocalPetId()
        if (self.__petDetailsContext is None and
                currentPetId and
                currentPetId in self.__petDetailsCallbacks):
            self.__startPetDetails(currentPetId)

    def __finishPetDetails(self, avatar):
        callbacksByPet = self.__petDetailsCallbacks
        self.__petDetailsCallbacks = {}
        self.__petDetailsContext = None
        self.__petDetailsPetId = 0
        for callbacks in list(callbacksByPet.values()):
            for callback in callbacks:
                callback(avatar)
