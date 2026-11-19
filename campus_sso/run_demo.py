# 2026-11-18 - David Noyes
# Start both local services with one shared environment.
# Run from the clone: python -m campus_sso.run_demo

import os
from pathlib import Path
from campus_sso.config import make_demo_environment
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def make_environment(source):
    return make_demo_environment(source)


def require_free_ports(ports=(5051, 5052)):
    # Normal startup checks the real ports.
    # Tests can supply an isolated temporary port.
    for port in ports:
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as error:
                raise RuntimeError(
                    f"Port {port} is already in use. "
                    "Stop its existing server first; no process was killed."
                ) from error


def stop_child(process):
    if process.poll() is not None:
        return

    if os.name == "nt":
        # Stop only the process tree created by this launcher.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_ready(children, timeout=15):
    pending = {
        "http://127.0.0.1:5051/campus",
        "http://127.0.0.1:5052/",
    }
    deadline = time.monotonic() + timeout

    while pending:
        if any(child.poll() is not None for child in children):
            raise RuntimeError(
                "A service stopped during startup. Read its traceback above."
            )

        for url in list(pending):
            try:
                with urlopen(url, timeout=0.5) as response:
                    if response.status == 200:
                        pending.remove(url)
            except (OSError, TimeoutError):
                pass

        if time.monotonic() >= deadline and pending:
            raise RuntimeError(
                "Startup timed out: " + ", ".join(sorted(pending))
            )

        if pending:
            time.sleep(0.1)


def main():
    children = []

    try:
        require_free_ports()
        env = make_environment(os.environ)

        for module in (
            "campus_sso.campus_provider",
            "backend.auth.campus_staff_app",
        ):
            options = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if os.name == "nt"
                else {}
            )

            children.append(
                subprocess.Popen(
                    [sys.executable, "-m", module],
                    cwd=ROOT,
                    env=env,
                    **options,
                )
            )

        wait_ready(children)

        print(
            "\nREADY: http://127.0.0.1:5051/campus",
            flush=True,
        )
        print(
            "Keep this terminal open. Ctrl+C stops both services. "
            "Secrets are not displayed.",
            flush=True,
        )

        while True:
            if any(child.poll() is not None for child in children):
                raise RuntimeError(
                    "A service stopped. Both services will be stopped; "
                    "read the error above."
                )
            time.sleep(0.25)

    except KeyboardInterrupt:
        print("\nStopping the campus demonstration.")
        return 0

    except (RuntimeError, OSError) as error:
        print(f"STARTUP ERROR: {error}", file=sys.stderr)
        return 1

    finally:
        for child in reversed(children):
            stop_child(child)


if __name__ == "__main__":
    raise SystemExit(main())
