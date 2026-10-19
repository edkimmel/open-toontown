from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectUD import DistributedObjectUD

CodeDoesntExist = 1

class TTCodeRedemptionMgrUD(DistributedObjectUD):
    notify = DirectNotifyGlobal.directNotify.newCategory('TTCodeRedemptionMgrUD')

    def redeemCode(self, context, code):
        avId = self.air.getAvatarIdFromSender()
        if not avId:
            return
        self.sendUpdateToAvatarId(avId, 'redeemCodeResult', [context, CodeDoesntExist, 0])
