from direct.directnotify import DirectNotifyGlobal
from otp.avatar import AvatarDetail
from toontown.pets import DistributedPet

class PetDetail(AvatarDetail.AvatarDetail):
    notify = DirectNotifyGlobal.directNotify.newCategory('PetDetail')

    def getDClass(self):
        return 'DistributedPet'

    def enterQuery(self):
        if not __astron__:
            return AvatarDetail.AvatarDetail.enterQuery(self)

        avatar = base.cr.doId2do.get(self.id)
        if avatar is not None and not avatar.ghostMode:
            self.avatar = avatar
            self.createdAvatar = 0
            self.callWhenDone(avatar)
            del self.callWhenDone
            return

        # Astron has no legacy 81/82 detail request.  Only the local Toon's
        # own durable pet can be fetched; remote/offline pets deliberately
        # fail closed rather than turning this into a public-details API.
        if (not hasattr(base, 'localAvatar') or
                base.localAvatar.getPetId() != self.id or
                base.cr.friendManager is None):
            self.callWhenDone(None)
            del self.callWhenDone
            return

        def gotDetails(avatar):
            self.avatar = avatar
            self.createdAvatar = 0
            self.callWhenDone(avatar)
            del self.callWhenDone

        base.cr.friendManager.requestOwnPetDetails(gotDetails)
        return

    def createHolder(self):
        pet = DistributedPet.DistributedPet(base.cr, bFake=True)
        pet.forceAllowDelayDelete()
        pet.generateInit()
        pet.generate()
        return pet
