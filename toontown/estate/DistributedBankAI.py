from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta

from toontown.estate import BankGlobals
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI


class DistributedBankAI(DistributedFurnitureItemAI):
    """One deposit/withdrawal session at a time, owner only.

    The bank stores no money of its own: it re-applies the same four
    clamps the client's transaction counter applies (BankGUI.py:74-77)
    against the entering avatar's own money/bankMoney fields.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedBankAI')

    def __init__(self, air, furnitureMgr, item, interiorIndex=None):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, item,
                                            interiorIndex=interiorIndex)
        self.customerId = 0

    def delete(self):
        self.ignoreAll()
        self.customerId = 0
        DistributedFurnitureItemAI.delete(self)

    def isBusy(self):
        return self.customerId != 0

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('avatarEnter from unknown avatar: %s' % avId)
            return

        ownerId = self.furnitureMgr.getOwnerId()
        if not ownerId:
            self.d_setMovie(BankGlobals.BANK_MOVIE_NO_OWNER, avId)
            return
        if avId != ownerId:
            self.d_setMovie(BankGlobals.BANK_MOVIE_NOT_OWNER, avId)
            return
        if self.isBusy():
            # the client has already put the toon into the banking state, so
            # an unanswered avatarEnter leaves it stuck there
            # (toontown/estate/DistributedBank.py:74-84)
            self.freeAvatar(avId)
            return

        self.customerId = avId
        self.d_setMovie(BankGlobals.BANK_MOVIE_GUI, avId)

    def transferMoney(self, amount):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.customerId:
            self.__reject(avId, 'transferMoney for a bank session belonging '
                          'to %s' % self.customerId)
            return
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('transferMoney from unknown avatar: %s' % avId)
            return

        amount = self.__clamp(av, amount)
        if amount == 0:
            self.__release(BankGlobals.BANK_MOVIE_NO_OP, avId)
            return

        av.b_setMoney(av.getMoney() - amount)
        av.b_setBankMoney(av.getBankMoney() + amount)
        mode = (BankGlobals.BANK_MOVIE_DEPOSIT if amount > 0
                else BankGlobals.BANK_MOVIE_WITHDRAW)
        self.__release(mode, avId)

    def freeAvatar(self, avId):
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])

    def d_setMovie(self, mode, avId):
        # the field is int16 (etc/toon.dc, DistributedBank.setMovie); the
        # default bits=16 keeps the value in range
        self.sendUpdate('setMovie', [mode, avId,
                                     globalClockDelta.getRealNetworkTime()])

    def __clamp(self, av, amount):
        # the same four limits BankGUI.__updateTransaction applies
        # client-side (BankGUI.py:74-77), re-applied so a forged amount
        # cannot move more than the jar/bank allow
        jarMoney = av.getMoney()
        maxJarMoney = av.getMaxMoney()
        bankMoney = av.getBankMoney()
        maxBankMoney = av.getMaxBankMoney()
        amount = min(amount, jarMoney)
        amount = min(amount, maxBankMoney - bankMoney)
        amount = -min(-amount, maxJarMoney - jarMoney)
        amount = -min(-amount, bankMoney)
        return amount

    def __release(self, mode, avId):
        self.customerId = 0
        self.d_setMovie(mode, avId)
        self.freeAvatar(avId)

    def __reject(self, avId, reason):
        self.notify.warning('%s: %s' % (avId, reason))
        self.air.writeServerEvent('suspicious', avId, reason)
