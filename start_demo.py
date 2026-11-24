"""Start a private, loopback-only copy of the Streamlit app on this computer."""
import json
import os
import secrets
import socket
import subprocess
import sys
import venv
from pathlib import Path


def main():
    if sys.version_info < (3, 11):
        sys.exit("Install Python 3.12 from python.org and run this launcher again.")
    os.chdir(Path(__file__).resolve().parent)
    env_dir = Path(".local/demo-venv")
    python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Setting up the demo on this computer…", flush=True)
        venv.create(env_dir, with_pip=True)
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                    "-q", "-r", "requirements.txt"], check=True)

    settings = Path(".streamlit/secrets.toml")
    if not settings.exists():
        password = secrets.token_urlsafe(18)
        settings.parent.mkdir(exist_ok=True)
        with os.fdopen(os.open(settings, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
            out.write(f'APP_PASSWORD = {json.dumps(password)}\nLOCAL_SQLITE_PATH = ".local/training.sqlite3"\n')
        print(f"Your new demo password (copy this to unlock the app): {password}", flush=True)
    else:
        print("Use your existing app password from .streamlit/secrets.toml.", flush=True)

    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 8514))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    print(f"Open http://127.0.0.1:{port}/ in Chrome. Keep this window open while using the app.", flush=True)
    subprocess.run([str(python), "-m", "streamlit", "run", "streamlit_app.py",
                    "--server.address=127.0.0.1", f"--server.port={port}", "--server.headless=false", "--server.showEmailPrompt=false",
                    "--browser.serverAddress=127.0.0.1", "--browser.gatherUsageStats=false"], check=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
