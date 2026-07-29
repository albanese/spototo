"""Environment-driven configuration for the Yoto pixel pipeline."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent


def _path(env_var: str, default: str) -> Path:
    return Path(os.environ.get(env_var, str(REPO_ROOT / default))).expanduser()


class Config:
    YOTO_CLIENT_ID = os.environ.get("YOTO_CLIENT_ID", "")
    YOTO_CARD_TITLE = os.environ.get("YOTO_CARD_TITLE", "Kids Playlist")
    YOTO_CARD_ID = os.environ.get("YOTO_CARD_ID", "")

    REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

    WATCH_DIR = _path("WATCH_DIR", "data/watch")
    PROCESSED_DIR = _path("PROCESSED_DIR", "data/processed")
    STATE_FILE = _path("STATE_FILE", "data/state.json")

    STABLE_WAIT_SECONDS = float(os.environ.get("STABLE_WAIT_SECONDS", "3"))

    YOTO_AUTH_BASE = os.environ.get("YOTO_AUTH_BASE", "https://login.yotoplay.com")
    YOTO_API_BASE = os.environ.get("YOTO_API_BASE", "https://api.yotoplay.com")
    YOTO_AUDIENCE = os.environ.get("YOTO_AUDIENCE", "https://api.yotoplay.com")
    YOTO_SCOPE = os.environ.get(
        "YOTO_SCOPE",
        "offline_access user:content:manage user:content:view user:icons:manage",
    )

    @classmethod
    def validate(cls):
        missing = [
            name
            for name in ("YOTO_CLIENT_ID", "REPLICATE_API_TOKEN")
            if not getattr(cls, name)
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        cls.WATCH_DIR.mkdir(parents=True, exist_ok=True)
        cls.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        cls.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
