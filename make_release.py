import os
import shutil
import subprocess
import sys

ROOT = r"C:\.Mono\Proektiki\LestnichnieBlini"
PY = r"C:\Users\zeroi\AppData\Local\Programs\Python\Python312\python.exe"
DIST = r"C:\.Mono\Proektiki\LB_releases"

os.chdir(ROOT)

# clean
if os.path.exists(DIST):
    try:
        shutil.rmtree(DIST)
    except Exception:
        pass
os.makedirs(DIST, exist_ok=True)
os.makedirs(os.path.join(DIST, "build"), exist_ok=True)

cmd = [
    PY,
    "-m",
    "PyInstaller",
    "--onefile",
    "--name",
    "LestnichnieBlini",
    "--distpath",
    DIST,
    "--workpath",
    os.path.join(DIST, "build"),
    "--specpath",
    DIST,
    "--add-data=game;game",
    "--add-data=levels;levels",
    "--add-data=sounds;sounds",
    "--add-data=libraries;libraries",
    "--add-data=shared;shared",
    "--hidden-import=pygame",
    "--hidden-import=pymunk",
    "--hidden-import=moderngl",
    "--hidden-import=numpy",
    "lb_entry.py",
]

r = subprocess.run(cmd, cwd=ROOT)
print("RC", r.returncode)
sys.exit(r.returncode)
