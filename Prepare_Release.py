"""Run after building an EXE: python Prepare_Release.py dist/KaamChor_Pro.exe VERSION HTTPS_URL"""
import hashlib
import json
from pathlib import Path
import sys
from app_updates import version, https_url, APP_VERSION

if __name__ == '__main__':
    if len(sys.argv) == 2:
        sys.argv.extend([APP_VERSION, 'https://github.com/KaamChor-prog/KaamChor-Updates/releases/download/v'+APP_VERSION+'/KaamChor_Pro.exe'])
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    path=Path(sys.argv[1]); version(sys.argv[2]); https_url(sys.argv[3])
    result={'version':sys.argv[2], 'url':sys.argv[3], 'size':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'notes':'Performance improvements and fixes.'}
    Path('latest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Created latest.json. Edit notes, upload EXE first, then latest.json.')
