from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI


class DistributedToonStatuaryAI(DistributedStatuaryAI):
    """A planted toon statuary (etc/toon.dc:2705) -- `setOptional` carries
    the toon DNA code chosen in `ToonStatueSelectionGUI` (etc/toon.dc:2706)."""

    def __init__(self, air, estateAI):
        DistributedStatuaryAI.__init__(self, air, estateAI)
        self.optional = 0

    def setOptional(self, optional):
        self.optional = optional

    def getOptional(self):
        return self.optional
