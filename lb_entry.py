import sys
import os

# Force map to The_Outskirts_v0.tar as requested
sys.argv = [
    os.path.basename(sys.argv[0]) if sys.argv else "LestnichnieBlini",
    "--map",
    "levels/The_Outskirts_v0.tar",
]

from main import main

if __name__ == "__main__":
    main()
