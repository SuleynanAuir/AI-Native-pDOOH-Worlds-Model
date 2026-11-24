"""Treat exited and zombie workers as dead, even before their parent reaps them."""
import os
import subprocess
import sys


def alive(pid):
    if type(pid) is not int or pid<=0:return False
    try:os.kill(pid,0)
    except ProcessLookupError:return False
    except PermissionError:return True
    try:
        if sys.platform.startswith('linux'):
            from pathlib import Path
            return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1][0]!='Z'
        state=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True,timeout=2).stdout.strip()
        return bool(state) and not state.startswith('Z')
    except (OSError,subprocess.SubprocessError):return True
