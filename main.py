import argparse
from game import Game

def main():
  p = argparse.ArgumentParser()
  p.add_argument("--cheats", action="store_true", help="infinite stamina and free air jump while space is held")
  p.add_argument("--map", default="levels/test.json", help="path to level json (default: levels/test.json)")
  p.add_argument("--debugview", action="store_true", help="overlay spawner markers and trigger zones")
  p.add_argument("--name", default=None, help="player name for multiplayer")
  p.add_argument("--server", default=None, help="websocket url, e.g. ws://example.com:8765")
  args = p.parse_args()
  if args.server and not args.name:
    p.error("--server requires --name")
  Game(cheats=args.cheats, map_path=args.map, debugview=args.debugview,
       name=args.name, server=args.server).run()

if __name__ == "__main__":
  main()
