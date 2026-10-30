@echo off
setlocal
set PY=C:\Users\zeroi\AppData\Local\Programs\Python\Python312\python.exe
set PROJ=C:\.Mono\Proektiki\LestnichnieBlini
set DIST=C:\.Mono\Proektiki\LB_releases
cd /d %PROJ%
if exist "%DIST%" rmdir /s /q "%DIST%"
mkdir "%DIST%"
mkdir "%DIST%\build"
"%PY%" -m PyInstaller --onefile --name LestnichnieBlini --distpath "%DIST%" --workpath "%DIST%\build" --specpath "%DIST%" --add-data "game;game" --add-data "levels;levels" --add-data "sounds;sounds" --add-data "libraries;libraries" --add-data "shared;shared" --add-data "editor;editor" --add-data "scripts;scripts" --add-data "net;net" --add-data "src;src" --add-data "docs;docs" --hidden-import pygame --hidden-import pymunk --hidden-import moderngl --hidden-import numpy lb_entry.py
endlocal
