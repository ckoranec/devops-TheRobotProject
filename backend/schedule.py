import os
import subprocess
import sys

def main():
    # gmu_map_api.py lives at the repo root, one level above this file
    folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if sys.platform == "win32":
        command = f'cmd /c cd /d "{folder}" && "{sys.executable}" gmu_map_api.py'
        result = subprocess.run(
            ["schtasks", "/create", "/tn", "MapAPI", "/tr", command,
             "/sc", "hourly", "/mo", "12", "/f"],
            capture_output=True, text=True,
        )
        print(result.stdout or result.stderr)
    else:
        cron_line = f'0 */12 * * * cd "{folder}" && "{sys.executable}" gmu_map_api.py'
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        if cron_line not in current:
            subprocess.run(["crontab", "-"], input=current + cron_line + "\n", text=True)
        print("Cron job installed.")

main()