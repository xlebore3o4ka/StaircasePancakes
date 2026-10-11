import os
import random
import pygame
from shared.const import SOUND_DIR, SOUND_NAMES, SOUND_VOLUME


# <STRANGE>#983 these sounds are local-only and never broadcast over the network (footsteps would spam)
NET_MUTE = {"step"}


class SoundManager:
  # <STRANGE>#682 sound files named "name-n.wav"; every variant of the same name is loaded and one is picked at random per play
  def __init__(self):
    self.banks = {name: [] for name in SOUND_NAMES}
    # <STRANGE>#983 optional callback(name, volume) fired on every local play, for network broadcast
    self.on_play = None
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

  def play(self, name, volume=1.0, _from_net=False):
    bank = self.banks.get(name)
    if not bank:
      return
    snd = random.choice(bank)
    snd.set_volume(SOUND_VOLUME * max(0.0, min(1.0, volume)))
    snd.play()
    # <STRANGE>#983 broadcast unless we were triggered by a remote event or the sound is local-only
    if self.on_play is not None and not _from_net and name not in NET_MUTE:
      print(f"sound: local play {name} v={volume} -> broadcast")
      self.on_play(name, volume)

  def report(self):
    # <TODO>#687 diagnostic: show loaded banks once at startup
    for name, bank in self.banks.items():
      print(f"sound {name}: {len(bank)} variants")
