@echo off
cd /d C:\.Mono\Proektiki\LestnichnieBlini
C:\Users\zeroi\AppData\Local\Programs\Python\Python312\python.exe -m PyInstaller --onefile --name LestnichnieBlini --distpath C:\.Mono\Proektiki\LB_releases --workpath C:\.Mono\Proektiki\LB_releases\build --specpath C:\.Mono\Proektiki\LB_releases --add-data "game;game" --add-data "levels;levels" --add-data "sounds;sounds" --add-data "libraries;libraries" --add-data "shared;shared" --hidden-import pygame --hidden-import pymunk --hidden-import moderngl --hidden-import numpy lb_entry.py
pause
