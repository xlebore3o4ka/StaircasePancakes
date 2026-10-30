import os
import sys
import shutil
import subprocess

os.chdir(r'C:\.Mono\Proektiki\LestnichnieBlini')
py = r'C:\Users\zeroi\AppData\Local\Programs\Python\Python312\python.exe'
dist = r'C:\.Mono\Proektiki\LB_releases'
if os.path.exists(dist):
    shutil.rmtree(dist, ignore_errors=True)
os.makedirs(dist, exist_ok=True)
os.makedirs(os.path.join(dist, 'build'), exist_ok=True)

cmd = [
    py, '-m', 'PyInstaller',
    '--onefile',
    '--name', 'LestnichnieBlini',
    '--distpath', dist,
    '--workpath', os.path.join(dist, 'build'),
    '--specpath', dist,
    '--add-data', r'game;game',
    '--add-data', r'levels;levels',
    '--add-data', r'sounds;sounds',
    '--add-data', r'libraries;libraries',
    '--add-data', r'shared;shared',
    '--hidden-import', 'pygame',
    '--hidden-import', 'pymunk',
    '--hidden-import', 'moderngl',
    '--hidden-import', 'numpy',
    'lb_entry.py'
]
r = subprocess.run(cmd)
sys.exit(r.returncode)
