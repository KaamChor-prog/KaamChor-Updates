"""HTTPS release feed and verified Windows single-file EXE updates."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen, Request
from urllib.parse import urlsplit

APP_VERSION = '3.4.2'
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


DOWNLOAD_TIMEOUT = 15
DOWNLOAD_DEADLINE = 180
DOWNLOAD_ATTEMPTS = 3


class DownloadCancelled(Exception):
    pass


def download_update(release, progress=None, cancel=None, status=None):
    """Read available bytes promptly; bound stalls, retries and total elapsed time."""
    folder = Path(tempfile.mkdtemp(prefix='KaamChor-update-'))
    target = folder / 'KaamChor_Pro.exe'
    started = time.monotonic()

    def check_cancelled():
        if cancel is not None and cancel.is_set():
            raise DownloadCancelled('Update cancelled. Existing app was not changed.')
        if time.monotonic() - started >= DOWNLOAD_DEADLINE:
            raise TimeoutError('Update download took too long. Please retry or download from the release page.')

    try:
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            check_cancelled()
            digest = hashlib.sha256()
            count = 0
            if progress: progress(0, release['size'])
            if status: status('Connecting to GitHub…' if attempt == 1 else f'Retrying download ({attempt}/{DOWNLOAD_ATTEMPTS})…')
            request = Request(https_url(release['url']), headers={
                'User-Agent': 'KaamChor-Pro/' + APP_VERSION,
                'Accept': 'application/octet-stream', 'Accept-Encoding': 'identity',
                'Cache-Control': 'no-cache'})
            try:
                with urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response, target.open('wb') as out:
                    https_url(response.geturl())
                    # read1 returns available data, instead of waiting to fill a large block.
                    read = getattr(response, 'read1', response.read)
                    while True:
                        check_cancelled()
                        chunk = read(64 * 1024)
                        check_cancelled()
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > release['size'] or count > MAX_EXE_BYTES:
                            raise ValueError('Download exceeds expected size.')
                        digest.update(chunk)
                        out.write(chunk)
                        if progress: progress(count, release['size'])
                if count != release['size']:
                    raise ConnectionError('Download was interrupted before all bytes arrived.')
                break
            except (OSError, URLError) as exc:
                check_cancelled()
                if attempt == DOWNLOAD_ATTEMPTS:
                    raise TimeoutError('GitHub download stalled or failed after 3 attempts. Please retry or use the release page.') from exc
        check_cancelled()
        if status: status('Verifying downloaded update…')
        if digest.hexdigest().lower() != release['sha256'].lower():
            raise ValueError('Download verification failed. Existing app was not changed.')
        with target.open('rb') as source:
            if source.read(2) != b'MZ':
                raise ValueError('Update is not a Windows executable.')
        check_cancelled()
        return target
    except Exception:
        target.unlink(missing_ok=True)
        folder.rmdir()
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
