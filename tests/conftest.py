import os
import sys
import tempfile
from pathlib import Path

import pytest

# Point the app at a throw-away SQLite database before it is imported.
_tmp = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.as_posix()}"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from seed.seed import main as seed_main  # noqa: E402


@pytest.fixture(scope="session")
def client():
    seed_main()
    with TestClient(app) as c:
        yield c


def _login(client, login, password):
    res = client.post("/api/auth/login", json={"login": login, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(scope="session")
def tokens(client):
    return {
        "admin": _login(client, "superadmin", "Admin@123"),
        "editor": _login(client, "editor", "Editor@123"),
        "moderator": _login(client, "moderator", "Moderator@123"),
        "seo": _login(client, "seo", "Seo@123"),
        "alice": _login(client, "alice", "User@123"),
        "bob": _login(client, "bob", "User@123"),
    }
