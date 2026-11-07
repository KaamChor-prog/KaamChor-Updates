# KaamChor Pro

Windows desktop app for Adobe Express school workflows.

Download the latest `KaamChor_Pro.exe` from Releases and open it. Chrome is required for browser automation.

## Themes

Choose Light, Dark, Navy Gold, Ocean Blue, Emerald or Purple from the header. Your selection is saved on this computer.

## Updates

Use Check for updates. Downloads show percentage and MB, support cancellation, retry interrupted connections up to three times, and verify the EXE size and SHA-256 before installation. Network reads use a 15-second timeout and downloads have a 180-second total deadline checked between reads. On failure the existing application remains available; retry or download directly from Releases.

## Build

Use Python 3.12 on Windows. Install requirements, run `python -m unittest discover -s tests -v`, then use Build_EXE.bat after creating the local .venv. GitHub Actions also builds and publishes the Windows EXE on main.

Never upload student spreadsheets, passwords or local settings to this public repository.
