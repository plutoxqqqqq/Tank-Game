"""Tiny procedural sound generator + optional .wav loading (asset-free, fail-safe)."""
from __future__ import annotations

import math
import os
import struct

import pygame

from tankgame.config import *


def load_optional_sound(path: str):
    try:
        if os.path.exists(path):
            return pygame.mixer.Sound(path)
    except Exception:
        pass
    return None


def generate_tone_sound(freq=440.0, duration=0.08, volume=0.25, sample_rate=44100):
    try:
        if not pygame.mixer.get_init():
            return None
        n = int(sample_rate * duration)
        buf = bytearray()
        amp = int(32767 * volume)
        two_pi = 2.0 * math.pi
        for i in range(n):
            t = i / sample_rate
            s = int(math.sin(two_pi * freq * t) * amp)
            buf += struct.pack("<h", s)
        return pygame.mixer.Sound(buffer=bytes(buf))
    except Exception:
        return None
