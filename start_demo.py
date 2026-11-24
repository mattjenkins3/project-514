"""Start the Cloudflare edition locally and carry forward an existing beta log."""
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parent


def main():
    os.chdir(ROOT)
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        sys.exit("Install Node.js 24 LTS, then run the launcher again.")
    if not Path("node_modules/wrangler/bin/wrangler.js").exists():
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], check=True)
    legacy = Path(".streamlit/secrets.toml")
    settings = tomllib.loads(legacy.read_text()) if legacy.exists() else {}
    dev_vars = Path(".dev.vars")
    if not dev_vars.exists():
        password = settings.get("APP_PASSWORD") or secrets.token_urlsafe(24)
        with os.fdopen(os.open(dev_vars, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
            out.write("APP_PASSWORD=" + json.dumps(password) + "\n")
    env = dict(os.environ, WRANGLER_SEND_METRICS="false", WRANGLER_LOG_PATH=str(ROOT / ".local/wrangler-logs"))
    Path(".local").mkdir(exist_ok=True, mode=0o700)
    cli = [node, "node_modules/wrangler/bin/wrangler.js"]
    subprocess.run([*cli, "d1", "migrations", "apply", "DB", "--local"], env=env, check=True)
    path = settings.get("LOCAL_SQLITE_PATH")
    if path and Path(path).is_file():
        with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as conn:
            rows = conn.execute("SELECT kind,day,payload FROM entry WHERE kind IN ('profile','plan','checkin','benchmark','rest','hold')")
            data = {}
            for kind, day, payload in rows:
                data.setdefault(kind, {})[day] = json.loads(payload)
        sql = subprocess.run([node, "worker/import-beta.js"], input=json.dumps(data), text=True,
                             capture_output=True, check=True).stdout
        if sql:
            with tempfile.NamedTemporaryFile(dir=".local", suffix=".sql", mode="w", delete=False) as tmp:
                tmp.write(sql)
            try:
                subprocess.run([*cli, "d1", "execute", "DB", "--local", "--file", tmp.name], env=env, check=True)
            finally:
                Path(tmp.name).unlink(missing_ok=True)
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 8514))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    print(f"Open http://127.0.0.1:{port}/ in Chrome. Find APP_PASSWORD in {dev_vars.resolve()}.", flush=True)
    os.execve(node, [*cli, "dev", "--local", "--ip", "127.0.0.1", "--port", str(port)], env)


if __name__ == "__main__":
    main()
