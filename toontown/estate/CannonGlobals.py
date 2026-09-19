CANNON_TIMEOUT = 20
CANNON_MOVIE_LOAD = 1
CANNON_MOVIE_CLEAR = 2
CANNON_MOVIE_FORCE_EXIT = 3
CANNON_MOVIE_LANDED = 4
cannonDrops = [(-110, -66, 0.025, -64, 0, 0),
 (65.68, -71.1, 0.025, 24, 0, 0),
 (-53.7788, -104.5, 0.72, -24, 0, 0),
 (39.58, 1.53, 8.2, 101.2, 0, 0),
 (61.3, 62.78, 0.031, 171.2, 0, 0),
 (-43.8, 75.2, 0.025, -158.15, 0, 0)]

# The client clamps its own aim to these before sending setCannonPosition /
# setCannonLit (DistributedCannon.py:33-37); the AI re-applies them rather
# than trusting the sender.
CANNON_ROTATION_MIN = -55
CANNON_ROTATION_MAX = 50
CANNON_ANGLE_MIN = 15
CANNON_ANGLE_MAX = 85

# How far a bumper may be dragged from ToontownGlobals.
# PinballCannonBumperInitialPos on each axis.  The reference bounds
# requestBumperMove nowhere; without a limit a client can park the bumper
# anywhere in the estate.
CANNON_BUMPER_MOVE_LIMIT = 60

# Where DistributedHouseAI.createCannon parks a cannon's target: this far in
# front of the cannon's `cannonDrops` entry, along its heading, and this far
# up.  The reference never places a target either.
TARGET_DISTANCE = 40
TARGET_HEIGHT = 20

# Broadcast by DistributedTargetAI on a hit.  The client's setReward handler
# only plays a sound (DistributedTarget.py:110-111) and the reference has no
# grant code, so nothing is credited.
TARGET_HIT_REWARD = 1
