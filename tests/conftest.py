import os
import sys
from pathlib import Path

import pytest

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db  # noqa: E402
from app.models import User  # noqa: E402


class TestConfig:
    SECRET_KEY = "test-secret"
    TESTING = True
    WTF_CSRF_ENABLED = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "connect_args": {"check_same_thread": False}}
    LOGIN_ATTEMPTS_LIMIT = 50
    LOGIN_LOCKOUT_PERIOD_MINUTES = 0
    POSTS_PER_PAGE = 10

    # Keep these off for tests unless explicitly enabled
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


@pytest.fixture()
def app():
    # Ensure self-ping never runs in tests
    os.environ["SELF_PING_ENABLED"] = "0"
    os.environ["SELF_PING_LEADER"] = "0"

    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        user = User(username="alice", email="alice@example.com")
        user.set_password("password123!")
        db.session.add(user)
        db.session.commit()

    yield app

    with app.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
