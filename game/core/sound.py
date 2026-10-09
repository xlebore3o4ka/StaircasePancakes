import os
import random
import pygame
from shared.const import SOUND_DIR, SOUND_NAMES, SOUND_VOLUME


class SoundManager:
  # <STRANGE>#682 sound files named "name-n.wav"; every variant of the same name is loaded and one is picked at random per play
  def __init__(self):
    self.banks = {name: [] for name in SOUND_NAMES}
    if not os.path.isdir(SOUND_DIR):
      return
    for fname in os.listdir(SOUND_DIR):
      if not fname.endswith(".wav"):
        continue
      stem = fname[:-4]
      if "-" not in stem:
        continue
      name, _, num = stem.rpartition("-")
      if not num.isdigit():
        continue
      if name not in self.banks:
        continue
      try:
        snd = pygame.mixer.Sound(os.path.join(SOUND_DIR, fname))
      except pygame.error:
        continue
      snd.set_volume(SOUND_VOLUME)
      self.banks[name].append(snd)

  def play(self, name):
    bank = self.banks.get(name)
    if not bank:
      return
    random.choice(bank).play()

  def report(self):
    # <TODO>#687 diagnostic: show loaded banks once at startup
    for name, bank in self.banks.items():
      print(f"sound {name}: {len(bank)} variants")
