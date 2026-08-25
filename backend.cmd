@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend.ps1" %*
