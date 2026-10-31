"""Application configuration, read from environment variables (or a local .env file)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so the project has no extra dependency for it."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

# Examples:
#   sqlite:///./newsportal.db                                   (default, zero setup)
#   postgresql+psycopg://postgres:postgres@localhost:5432/newsportal
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'newsportal.db').as_posix()}")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))
STATIC_DIR = BASE_DIR / "static"
