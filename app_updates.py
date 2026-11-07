"""HTTPS release feed and verified Windows single-file EXE updates."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.request import urlopen, Request
from urllib.parse import urlsplit

APP_VERSION = '3.4.1'
# Set once before building the first update-enabled release. Never put tokens here.
UPDATE_FEED_URL = 'https://github.com/KaamChor-prog/KaamChor-Updates/releases/latest/download/latest.json'
MAX_EXE_BYTES = 500 * 1024 * 1024


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Version must use major.minor.patch format.')
    return tuple(map(int, value.split('.')))


def https_url(value):
    if not isinstance(value, str):
        raise ValueError('Missing HTTPS address.')
    parts = urlsplit(value)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise ValueError('Update addresses must use HTTPS without credentials.')
    return value


def fetch_json(url):
    request = Request(https_url(url), headers={'Cache-Control':'no-cache', 'Pragma':'no-cache', 'User-Agent':'KaamChor-Pro/'+APP_VERSION})
    with urlopen(request, timeout=15) as response:
        https_url(response.geturl())
        data = response.read(65537)
    if len(data) > 65536:
        raise ValueError('Release information is too large.')
    return json.loads(data)


def check_update():
    if not UPDATE_FEED_URL:
        raise ValueError('Update service is not configured in this build.')
    release = fetch_json(UPDATE_FEED_URL)
    if not isinstance(release, dict):
        raise ValueError('Invalid release information.')
    newer = version(release.get('version')) > version(APP_VERSION)
    if not newer:
        return None
    https_url(release.get('url'))
    if not re.fullmatch('[0-9a-fA-F]{64}', release.get('sha256', '')):
        raise ValueError('Missing or invalid download checksum.')
    if type(release.get('size')) is not int or not 0 < release['size'] <= MAX_EXE_BYTES:
        raise ValueError('Invalid release size.')
    if not isinstance(release.get('notes', ''), str):
        raise ValueError('Invalid release notes.')
    return release


def download_update(release, progress=None):
    folder = Path(tempfile.mkdtemp(prefix='KaamChor-update-'))
    target = folder / 'KaamChor_Pro.exe'
    digest = hashlib.sha256()
    count = 0
    try:
        if progress: progress(0, release['size'])
        with urlopen(https_url(release['url']), timeout=30) as response, target.open('wb') as out:
            https_url(response.geturl())
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > release['size'] or count > MAX_EXE_BYTES:
                    raise ValueError('Download exceeds expected size.')
                digest.update(chunk)
                out.write(chunk)
                if progress: progress(count, release['size'])
        if count != release['size'] or digest.hexdigest().lower() != release['sha256'].lower():
            raise ValueError('Download verification failed. Existing app was not changed.')
        with target.open('rb') as source:
            if source.read(2) != b'MZ':
                raise ValueError('Update is not a Windows executable.')
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


def install_update(download):
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        raise ValueError('Install updates from the Windows EXE build.')
    target = Path(sys.executable).resolve()
    staged = Path(download).resolve()
    # Paths are data arguments, never interpolated into PowerShell source.
    script = staged.parent / 'install.ps1'
    script.write_text('''param([int]$AppPid,[string]$Source,[string]$Target)
$ErrorActionPreference = 'Stop'
$backup = $Target + '.previous'
$replaced = $false
try {
    $process = Get-Process -Id $AppPid -ErrorAction SilentlyContinue
    if ($process) { $process.WaitForExit() }
    # PyInstaller one-file launcher can retain its executable after child exit.
    # Wait for an exclusive handle without terminating any user process.
    $deadline = (Get-Date).AddSeconds(90)
    while ($true) {
        $handle = $null
        try {
            $handle = [System.IO.File]::Open($Target, 'Open', 'ReadWrite', 'None')
            break
        } catch {
            if ((Get-Date) -gt $deadline) { throw 'App file is still in use. Close all KaamChor windows and retry.' }
            Start-Sleep -Milliseconds 500
        } finally {
            if ($handle) { $handle.Dispose() }
        }
    }
    Copy-Item -LiteralPath $Target -Destination $backup -Force
    $pending = $Target + '.update-' + [guid]::NewGuid().ToString()
    Copy-Item -LiteralPath $Source -Destination $pending
    $deadline = (Get-Date).AddSeconds(30)
    while ($true) {
        try {
            # Atomic replacement avoids a partially overwritten executable.
            [System.IO.File]::Replace($pending, $Target, $null)
            $replaced = $true
            break
        } catch {
            if ((Get-Date) -gt $deadline) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
    # PyInstaller must start as a fresh application, not a subprocess of old bundle.
    Remove-Item Env:_MEIPASS2 -ErrorAction SilentlyContinue
    Remove-Item Env:_PYI_APPLICATION_HOME_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:_PYI_PARENT_PROCESS_LEVEL -ErrorAction SilentlyContinue
    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
    Start-Process -FilePath $Target
} catch {
    $detail = $_.Exception.Message
    if ($replaced) {
        try { Copy-Item -LiteralPath $backup -Destination $Target -Force }
        catch { $detail += ' Previous version backup: ' + $backup }
    }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show('Update could not be installed. Previous version is available at the app path or .previous backup. ' + $detail, 'KaamChor Pro Update') | Out-Null
}
''', encoding='utf-8')
    subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                      str(script), str(os.getpid()), str(staged), str(target)],
                     creationflags=subprocess.CREATE_NO_WINDOW)
