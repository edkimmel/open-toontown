from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from otp.otpbase import OTPGlobals

class FriendManagerAI(DistributedObjectAI):
    """Server half of `otp/friends/FriendManager.py` (dclass
    `etc/otp.dc:308-322`), generated at the fixed doId 4501 by
    `toontown/ai/ToontownAIRepository.createGlobals`, matching the client's
    `cr.generateGlobalObject(OTP_DO_ID_FRIEND_MANAGER, 'FriendManager')`
    (`toontown/toonbase/ToontownStart.py`). astrond.yml must reserve 4501 as
    an uberdog or the client agent rejects any update sent to it.

    The two code tables this class must obey, both read off the client
    (`toontown/friends/FriendInviter.py:498-532`):

      `friendConsidering(int8, int32)`: 1 asking, 0 notAvailable, 2 already,
        3 self, 4 ignored, 6 notAcceptingFriends, 10 no, 13 otherTooMany;
        anything else -> maybe.

      `friendResponse(int8, int32)`: 1 yes, 0 no, 3 otherTooMany; anything
        else -> maybe.

    The *invitee* only ever sends 0 (no), 1 (yes), 2 (dialog torn down
    without an answer) and 3 (its own list is already at MaxFriends)
    (`toontown/friends/FriendInvitee.py:19-70`).  3 lines up with the
    inviter's `otherTooMany` and passes through; 2 does not appear in the
    inviter's table at all and must be translated, or the inviter falls
    into `maybe`.

    `requestSecret` / `submitSecret` (`etc/otp.dc:318-321`) are not
    implemented here.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('FriendManagerAI')

    # friendConsidering codes (FriendInviter.py:498-518)
    CONSIDERING_ASKING = 1
    CONSIDERING_NOT_AVAILABLE = 0
    CONSIDERING_ALREADY = 2
    CONSIDERING_SELF = 3
    CONSIDERING_IGNORED = 4
    CONSIDERING_NOT_ACCEPTING = 6
    CONSIDERING_NO = 10
    CONSIDERING_OTHER_TOO_MANY = 13

    # friendResponse codes (FriendInviter.py:520-532)
    RESPONSE_NO = 0
    RESPONSE_YES = 1
    RESPONSE_OTHER_TOO_MANY = 3

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        # context -> (inviterId, inviteeId).  The reference client puts no
        # timeout on friendQuery, so a context lives until it is answered,
        # cancelled, or one of the two toons leaves the shard.
        self.invites = {}
        self.nextContext = 1

    def _allocateContext(self):
        context = self.nextContext
        # int32 on the wire (etc/otp.dc:309-317).
        self.nextContext = self.nextContext + 1 if self.nextContext < 0x7FFFFFFF else 1
        return context

    def _getToon(self, avId):
        return self.air.doId2do.get(avId)

    def _friendsList(self, toon):
        return toon.getFriendsList() or []

    def _isFriendOf(self, toon, otherId):
        # Entries are (friendId, friendCode) pairs (etc/otp.dc:227-230).
        for pair in self._friendsList(toon):
            if pair[0] == otherId:
                return True

        return False

    def _sendConsidering(self, avId, code, context):
        self.sendUpdateToAvatarId(avId, 'friendConsidering', [code, context])

    def _sendResponse(self, avId, code, context):
        self.sendUpdateToAvatarId(avId, 'friendResponse', [code, context])

    # client -> AI (airecv clsend, etc/otp.dc:309-313)
    def friendQuery(self, inviteeId):
        """`FriendManager.up_friendQuery`, sent from
        `FriendInviter.enterCheckAvailability`."""
        inviterId = self.air.getAvatarIdFromSender()
        inviter = self._getToon(inviterId)
        if inviter is None:
            self.notify.warning('friendQuery from unknown avatar %s' % inviterId)
            return

        context = self._allocateContext()

        if inviteeId == inviterId:
            self._sendConsidering(inviterId, self.CONSIDERING_SELF, context)
            return

        if self._isFriendOf(inviter, inviteeId):
            self._sendConsidering(inviterId, self.CONSIDERING_ALREADY, context)
            return

        invitee = self._getToon(inviteeId)
        if invitee is None:
            # Not online, or on another district.
            self._sendConsidering(inviterId, self.CONSIDERING_NOT_AVAILABLE, context)
            return

        if len(self._friendsList(invitee)) >= OTPGlobals.MaxFriends:
            self._sendConsidering(inviterId, self.CONSIDERING_OTHER_TOO_MANY, context)
            return

        self.invites[context] = (inviterId, inviteeId)
        # inviteeFriendQuery(int32 inviterId, string inviterName,
        # blob inviterDna, int32 context) -- etc/otp.dc:316, handled at
        # FriendManager.py:77-93.
        self.sendUpdateToAvatarId(inviteeId, 'inviteeFriendQuery',
                                  [inviterId, inviter.getName(), inviter.getDNAString(), context])

    def inviteeFriendConsidering(self, yesNo, context):
        """`FriendManager.up_inviteeFriendConsidering`, auto-sent by the
        invitee from inside `inviteeFriendQuery`."""
        senderId = self.air.getAvatarIdFromSender()
        invite = self.invites.get(context)
        if invite is None:
            self.notify.warning('inviteeFriendConsidering for dead context %s' % context)
            return

        inviterId, inviteeId = invite
        if senderId != inviteeId:
            self.notify.warning('inviteeFriendConsidering from %s, not invitee %s' % (senderId, inviteeId))
            return

        # The invitee's own codes are already inviter-table values except
        # for the cases below, which are not in the inviter's table
        # (FriendInviter.py:498-518) and must be clamped to notAvailable
        # rather than let the inviter fall through to 'maybe'.
        if yesNo not in (self.CONSIDERING_ASKING,
                         self.CONSIDERING_NOT_AVAILABLE,
                         self.CONSIDERING_IGNORED,
                         self.CONSIDERING_NOT_ACCEPTING):
            self.notify.warning('unexpected inviteeFriendConsidering code %s' % yesNo)
            yesNo = self.CONSIDERING_NOT_AVAILABLE

        self._sendConsidering(inviterId, yesNo, context)
        if yesNo != self.CONSIDERING_ASKING:
            # No dialog was raised on the invitee, so no response is coming.
            del self.invites[context]

    def inviteeFriendResponse(self, yesNoMaybe, context):
        """`FriendManager.up_inviteeFriendResponse`, sent by
        `FriendInvitee`."""
        senderId = self.air.getAvatarIdFromSender()
        invite = self.invites.get(context)
        if invite is None:
            self.notify.warning('inviteeFriendResponse for dead context %s' % context)
            return

        inviterId, inviteeId = invite
        if senderId != inviteeId:
            self.notify.warning('inviteeFriendResponse from %s, not invitee %s' % (senderId, inviteeId))
            return

        del self.invites[context]

        if yesNoMaybe == self.RESPONSE_YES:
            if self.makeFriends(inviterId, inviteeId):
                self._sendResponse(inviterId, self.RESPONSE_YES, context)
            else:
                self._sendResponse(inviterId, self.RESPONSE_NO, context)
            return

        if yesNoMaybe == self.RESPONSE_OTHER_TOO_MANY:
            # The invitee's own list was already at MaxFriends
            # (FriendInvitee.py:19-20); passes straight through.
            self._sendResponse(inviterId, self.RESPONSE_OTHER_TOO_MANY, context)
            return

        # 0 is an explicit no.  2 (dialog torn down without an answer) is
        # not in the inviter's table (FriendInviter.py:530-532); translate
        # it, and anything else, to no.
        if yesNoMaybe != self.RESPONSE_NO:
            self.notify.debug('translating inviteeFriendResponse %s to no' % yesNoMaybe)
        self._sendResponse(inviterId, self.RESPONSE_NO, context)

    def cancelFriendQuery(self, context):
        """`FriendManager.up_cancelFriendQuery`, sent from
        `FriendInviter.enterWentAway`/`enterCancel`."""
        senderId = self.air.getAvatarIdFromSender()
        invite = self.invites.get(context)
        if invite is None:
            self.notify.warning('cancelFriendQuery for dead context %s' % context)
            return

        inviterId, inviteeId = invite
        if senderId != inviterId:
            self.notify.warning('cancelFriendQuery from %s, not inviter %s' % (senderId, inviterId))
            return

        # The client acknowledges from
        # FriendManager.inviteeCancelFriendQuery; the record stays until
        # that ack arrives.
        self.sendUpdateToAvatarId(inviteeId, 'inviteeCancelFriendQuery', [context])

    def inviteeAcknowledgeCancel(self, context):
        """`FriendManager.up_inviteeAcknowledgeCancel`, sent from
        `FriendManager.inviteeCancelFriendQuery`."""
        senderId = self.air.getAvatarIdFromSender()
        invite = self.invites.get(context)
        if invite is None:
            return

        inviterId, inviteeId = invite
        if senderId != inviteeId:
            self.notify.warning('inviteeAcknowledgeCancel from %s, not invitee %s' % (senderId, inviteeId))
            return

        del self.invites[context]

    def makeFriends(self, avId, otherId, friendCode=0):
        """Two-way friendship between two toons that are both on this AI.

        `extendFriendsList` mutates the list in place
        (`toontown/toon/DistributedToonAI.py:611-618`); `b_setFriendsList`
        then stores it and sends the field update.  `setFriendsList` is a
        `db` field (`etc/otp.dc:245`) on an activated object, so that one
        update is what the database keeps -- the same path `b_setMoney`
        takes (`DistributedToonAI.py:2431-2438`).
        """
        toon = self._getToon(avId)
        other = self._getToon(otherId)
        if toon is None or other is None:
            self.notify.warning('makeFriends(%s, %s): not both on this AI' % (avId, otherId))
            return False

        if len(self._friendsList(toon)) >= OTPGlobals.MaxFriends and not self._isFriendOf(toon, otherId):
            return False
        if len(self._friendsList(other)) >= OTPGlobals.MaxFriends and not self._isFriendOf(other, avId):
            return False

        toon.extendFriendsList(otherId, friendCode)
        other.extendFriendsList(avId, friendCode)
        toon.b_setFriendsList(toon.getFriendsList())
        other.b_setFriendsList(other.getFriendsList())
        return True

    def forgetAvatar(self, avId):
        """Drop any pending invite that mentions an avatar that has left."""
        for context in [c for c, pair in self.invites.items() if avId in pair]:
            del self.invites[context]

    # The friends-list fetch (`getFriendsListRequest` /
    # `getFriendsListResponse`, `etc/otp.dc`).  This is what the client needs
    # for a friend that is *not* generated to it: name, DNA and pet id, the
    # same payload the legacy `CLIENT_GET_FRIEND_LIST` reply carried
    # (`toontown/distributed/ToontownClientRepository.py:902-911`).
    def getFriendsListRequest(self):
        avId = self.air.getAvatarIdFromSender()
        av = self._getToon(avId)
        if av is None:
            self.notify.warning('getFriendsListRequest from unknown avatar %s' % avId)
            self._sendFriendsList(avId, 1, [])
            return

        details = []
        offline = []
        for pair in self._friendsList(av):
            friend = self._getToon(pair[0])
            if friend is None:
                offline.append(pair[0])
            else:
                details.append([pair[0], friend.getName(), friend.getDNAString(),
                                self._getPetId(friend)])

        if not offline:
            self._sendFriendsList(avId, 0, details)
            return

        # The rest are not on this AI, so their fields only exist in the
        # database (`otp/login/AstronLoginManagerUD.py:533-540` is the same
        # query shape).
        remaining = [len(offline)]

        def makeCallback(friendId):

            def gotFriend(dclass, fields):
                remaining[0] -= 1
                if fields and dclass == self.air.dclassesByName['DistributedToonUD']:
                    details.append([friendId,
                                    fields['setName'][0],
                                    fields['setDNAString'][0],
                                    fields.get('setPetId', (0,))[0]])
                else:
                    self.notify.warning('no database row for friend %s' % friendId)
                if not remaining[0]:
                    self._sendFriendsList(avId, 0, details)

            return gotFriend

        for friendId in offline:
            self.air.dbInterface.queryObject(self.air.dbId, friendId,
                                             makeCallback(friendId))

    def _getPetId(self, toon):
        # `getPetId` only exists when pets are wanted
        # (`toontown/toon/DistributedToonAI.py:3018-3021`).
        if hasattr(toon, 'getPetId'):
            return toon.getPetId()

        return 0

    def _sendFriendsList(self, avId, errorCode, details):
        self.sendUpdateToAvatarId(avId, 'getFriendsListResponse',
                                  [errorCode, details])