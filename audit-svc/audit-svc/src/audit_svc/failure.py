import random

FAILURE_CHANCE = 0.1


def inject_failure():
    value = random.random()
    if value < FAILURE_CHANCE:
        raise RuntimeError("random failure")
