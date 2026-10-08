import argparse
from game import Game

def main():
  p = argparse.ArgumentParser()
  p.add_argument("--cheats", action="store_true", help="infinite stamina and free air jump while space is held")
  args = p.parse_args()
  Game(cheats=args.cheats).run()

if __name__ == "__main__":
  main()
