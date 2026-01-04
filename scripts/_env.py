from pathlib import Path

def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        # do not overwrite existing env vars
        import os
        os.environ.setdefault(k, v)

#import os
#from pathlib import Path
#from _env import load_dotenv

#load_dotenv(Path(__file__).resolve().parents[1] / ".env")

#WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
#if not WEBHOOK:
#    raise SystemExit("Missing DISCORD_WEBHOOK_URL")
