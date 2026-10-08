import argparse
from game import Game

def main():
  p = argparse.ArgumentParser()
  p.add_argument("--cheats", action="store_true", help="infinite stamina and free air jump while space is held")
  p.add_argument("--map", default="levels/test.json", help="path to level json (default: levels/test.json)")
  p.add_argument("--spawninfo", action="store_true", help="overlay item spawner markers and nearby entries")
  args = p.parse_args()
  Game(cheats=args.cheats, map_path=args.map, spawninfo=args.spawninfo).run()

if __name__ == "__main__":
  main()
