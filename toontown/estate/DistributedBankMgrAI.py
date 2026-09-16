from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import BankGlobals


class DistributedBankMgrAI(DistributedObjectAI):
    """The anywhere twin of DistributedBankAI.

    A single global object the client parks on `base.cr.bankManager`
    (DistributedBankMgr.py:12-17). Unlike the in-house bank there is no
    session and no movie: `transferMoney(amount)` moves money for
    whichever avatar sent it, clamped by the same rule.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedBankMgrAI')

    def transferMoney(self, amount):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            self.notify.warning('transferMoney from unknown avatar: %s' % avId)
            return

        amount = BankGlobals.clampTransfer(av, amount)
        if amount == 0:
            return

        av.b_setMoney(av.getMoney() - amount)
        av.b_setBankMoney(av.getBankMoney() + amount)
