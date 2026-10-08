import argparse
from game import Game

def main():
  p = argparse.ArgumentParser()
  p.add_argument("--cheats", action="store_true", help="infinite stamina and free air jump while space is held")
  p.add_argument("--map", default="levels/test.json", help="path to level json (default: levels/test.json)")
  args = p.parse_args()
  Game(cheats=args.cheats, map_path=args.map).run()

if __name__ == "__main__":
  main()
