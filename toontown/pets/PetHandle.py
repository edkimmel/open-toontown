from toontown.toonbase import ToontownGlobals
from toontown.pets import PetMood, PetTraits


class PetDetailsAvatar:
    """Non-generated owner-pet DTO holder for the Astron FriendManager RPC."""

    def __init__(self, cr, petId, details):
        (self.ownerId, self.name, self.traitSeed, self.safeZone, traitValues,
         head, ears, nose, tail, bodyTexture, color, colorScale, eyeColor,
         gender, self.lastSeenTimestamp, moodValues,
         self.trickAptitudes) = details
        self.doId = petId
        self.style = [head, ears, nose, tail, bodyTexture, color, colorScale,
                      eyeColor, gender]
        self.cr = cr
        self.bFake = True
        self.traitList = list(traitValues)
        self.traits = PetTraits.PetTraits(self.traitSeed, self.safeZone,
                                          traitValueList=self.traitList)
        self.lastKnownMood = PetMood.PetMood(self)
        for name, value in zip(PetMood.PetMood.Components, moodValues):
            self.lastKnownMood.setComponent(name, value, announce=0)

    def getName(self):
        return self.name

    def getDNA(self):
        return self.style

    # AvatarDetail callers historically clean up a generated fake pet.  The
    # DTO is never generated or placed in the CR, so cleanup is deliberately
    # inert while preserving that caller contract.
    def disable(self):
        pass

    def delete(self):
        pass

    def detectLeaks(self):
        pass

class PetHandle:

    def __init__(self, avatar):
        self.doId = avatar.doId
        self.name = avatar.name
        self.style = avatar.style
        self.ownerId = avatar.ownerId
        self.bFake = False
        self.cr = avatar.cr
        self.traits = PetTraits.PetTraits(avatar.traitSeed, avatar.safeZone, traitValueList=avatar.traitList)
        self._grabMood(avatar)

    def _grabMood(self, avatar):
        self.mood = avatar.lastKnownMood.makeCopy()
        self.mood.setPet(self)
        self.lastKnownMood = self.mood.makeCopy()
        self.setLastSeenTimestamp(avatar.lastSeenTimestamp)
        self.updateOfflineMood()

    def getDoId(self):
        return self.doId

    def getOwnerId(self):
        return self.ownerId

    def isPet(self):
        return True

    def getName(self):
        return self.name

    def getDNA(self):
        return self.style

    def getFont(self):
        return ToontownGlobals.getToonFont()

    def setLastSeenTimestamp(self, timestamp):
        self.lastSeenTimestamp = timestamp

    def getTimeSinceLastSeen(self):
        t = self.cr.getServerTimeOfDay() - self.lastSeenTimestamp
        return max(0.0, t)

    def updateOfflineMood(self):
        self.mood.driftMood(dt=self.getTimeSinceLastSeen(), curMood=self.lastKnownMood)

    def getDominantMood(self):
        if not hasattr(self, 'mood'):
            return PetMood.PetMood.Neutral
        return self.mood.getDominantMood()

    def uniqueName(self, idString):
        return idString + '-' + str(self.getDoId())

    def updateMoodFromServer(self, callWhenDone = None):

        # Keep the snapshot DTO importable before GUI-heavy DistributedPet
        # modules load.  This legacy detail helper is only needed on demand.
        from toontown.pets import PetDetail

        def handleGotDetails(avatar, callWhenDone = callWhenDone):
            if avatar is not None:
                self._grabMood(avatar)
            if callWhenDone:
                callWhenDone()

        PetDetail.PetDetail(self.doId, handleGotDetails)
