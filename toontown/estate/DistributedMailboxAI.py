from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogItem
from toontown.estate import MailboxGlobals
from toontown.toonbase import ToontownGlobals


class DistributedMailboxAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedMailboxAI')

    def __init__(self, air, house):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.fullIndicator = 0
        self.busy = 0

    def getHouseId(self):
        # the client compares this against its own houseId before it accepts
        # the collision (toontown/estate/DistributedMailbox.py:37-38)
        return self.house.doId

    def getHousePos(self):
        return self.house.getHousePos()

    def getName(self):
        return self.house.getName()

    def getFullIndicator(self):
        return self.fullIndicator

    def b_setFullIndicator(self, full):
        self.fullIndicator = full
        self.sendUpdate('setFullIndicator', [full])

    def delete(self):
        self.ignoreAll()
        self.busy = 0
        DistributedObjectAI.delete(self)

    def isBusy(self):
        return self.busy > 0

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('avatarEnter from unknown avatar: %s' % avId)
            return
        if self.isBusy():
            self.freeAvatar(avId)
            return
        if av.houseId != self.house.doId:
            # the client only opens its owner's mailbox
            # (toontown/estate/DistributedMailbox.py:39-40)
            self.d_setMovie(MailboxGlobals.MAILBOX_MOVIE_NOT_OWNER, avId)
            self.freeAvatar(avId)
            return
        if not self.__numItems(av):
            if len(av.onOrder) or len(av.onGiftOrder):
                mode = MailboxGlobals.MAILBOX_MOVIE_WAITING
            else:
                mode = MailboxGlobals.MAILBOX_MOVIE_EMPTY
            self.d_setMovie(mode, avId)
            self.freeAvatar(avId)
            return
        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleUnexpectedExit, extraArgs=[avId])
        if av.mailboxNotify == ToontownGlobals.NewItems:
            # the mail is being read now, so the button stops advertising it,
            # the same downgrade the catalog does when it is opened
            # (toontown/toon/DistributedToon.py:1126-1127, LocalToon.py:1161)
            av.b_setCatalogNotify(av.catalogNotify, ToontownGlobals.OldItems)
        self.d_setMovie(MailboxGlobals.MAILBOX_MOVIE_READY, avId)

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busy != avId:
            if self.busy != 0:
                self.air.writeServerEvent('suspicious', avId, 'DistributedMailboxAI.avatarExit busy with %s' % self.busy)
            return
        self.__release(MailboxGlobals.MAILBOX_MOVIE_EXIT)

    def freeAvatar(self, avId):
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId])

    def acceptItemMessage(self, context, blob, index, optional):
        avId = self.air.getAvatarIdFromSender()
        retcode = self.__acceptItem(avId, bytes(blob), index, optional)
        self.sendUpdateToAvatarId(avId, 'acceptItemResponse', [context, retcode])

    def discardItemMessage(self, context, blob, index, optional):
        avId = self.air.getAvatarIdFromSender()
        retcode = self.__discardItem(avId, bytes(blob), index)
        self.sendUpdateToAvatarId(avId, 'discardItemResponse', [context, retcode])

    def __acceptItem(self, avId, blob, index, optional):
        av = self.__shopper(avId, 'acceptItemMessage')
        if av is None:
            return ToontownGlobals.P_NotAtMailbox
        contents, offset, retcode = self.__findItem(av, blob, index)
        if retcode is not None:
            return retcode
        item = contents[offset]
        retcode = item.recordPurchase(av, optional)
        if retcode != ToontownGlobals.P_ItemAvailable:
            # a full closet or a missing trunk leaves the item in the mailbox
            # so the owner can take it once there is room
            # (toontown/catalog/MailboxScreen.py:253-259)
            return retcode
        self.__consume(av, contents, offset)
        return retcode

    def __discardItem(self, avId, blob, index):
        av = self.__shopper(avId, 'discardItemMessage')
        if av is None:
            return ToontownGlobals.P_NotAtMailbox
        contents, offset, retcode = self.__findItem(av, blob, index)
        if retcode is not None:
            return retcode
        # nothing is granted and nothing is refunded: the item was paid for
        # when it was ordered
        self.__consume(av, contents, offset)
        return ToontownGlobals.P_ItemAvailable

    def __shopper(self, avId, message):
        if self.busy != avId:
            self.air.writeServerEvent('suspicious', avId, 'DistributedMailboxAI.%s while not at the mailbox' % message)
            return None
        return self.air.doId2do.get(avId)

    def __findItem(self, av, blob, index):
        """Resolves a client index into the list the entry actually lives in.

        The screen shows the award items first and the mailbox items after
        them (toontown/catalog/MailboxScreen.py:503-512), so an index past the
        awards belongs to the second list.  The submitted blob must still
        match the entry found there: the two lists change under the screen
        whenever a delivery lands, and a stale or reordered selection must not
        take a different item.
        """
        awards = av.awardMailboxContents
        if index < len(awards):
            contents = awards
            offset = index
        else:
            contents = av.mailboxContents
            offset = index - len(awards)
        if offset < 0 or offset >= len(contents):
            return (None, None, ToontownGlobals.P_InvalidIndex)
        if contents[offset].getBlob(store=CatalogItem.Customization) != blob:
            return (None, None, ToontownGlobals.P_InvalidIndex)
        return (contents, offset, None)

    def __consume(self, av, contents, offset):
        del contents[offset]
        if contents is av.awardMailboxContents:
            av.b_setAwardMailboxContents(contents)
        else:
            av.b_setMailboxContents(contents)
        if not self.__numItems(av):
            av.b_setCatalogNotify(av.catalogNotify, ToontownGlobals.NoItems)
        av.checkMailboxFullIndicator()

    def __numItems(self, av):
        # what the screen will have to show (MailboxScreen.py:503-512) and
        # what the flag is raised for
        # (toontown/toon/DistributedToonAI.py:2323-2328)
        return (len(av.mailboxContents) + len(av.awardMailboxContents)
                + av.numMailItems + av.getNumInvitesToShowInMailbox())

    def __release(self, mode):
        avId = self.busy
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.busy = 0
        self.d_setMovie(mode, avId)
        if avId in self.air.doId2do:
            self.freeAvatar(avId)

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar %s exited unexpectedly' % avId)
        if self.busy != avId:
            return
        self.__release(MailboxGlobals.MAILBOX_MOVIE_CLEAR)
