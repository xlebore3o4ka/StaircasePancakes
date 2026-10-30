import os
import sys
import subprocess

os.chdir(r"C:\.Mono\Proektiki\LestnichnieBlini")
py = r"C:\Users\zeroi\AppData\Local\Programs\Python\Python312\python.exe"
dist = r"C:\.Mono\Proektiki\LB_releases"
work = os.path.join(dist, "build")
spec = dist
cmd = [
    py, "-m", "PyInstaller",
    "--onefile",
    "--name", "LestnichnieBlini",
    "--distpath", dist,
    "--workpath", work,
    "--specpath", spec,
    "--add-data", "game;game",
    "--add-data", "levels;levels", 
    "--add-data", "sounds;sounds",
    "--add-data", "libraries;libraries",
    "--add-data", "shared;shared",
    "--hidden-import", "pygame",
    "--hidden-import", "pymunk",
    "--hidden-import", "moderngl",
    "--hidden-import", "numpy",
    "lb_entry.py"
]
r = subprocess.run(cmd)
sys.exit(r.returncode)
