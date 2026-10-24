@echo off
rem Double-click to start Job Tracker. Extra arguments (e.g. --browser) are passed through.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
