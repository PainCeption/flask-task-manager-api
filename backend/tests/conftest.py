
import importlib
import sys
from pathlib import Path

import pytest


# Make sure Python can import app.py and database.py
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Give the test application a JWT signing secret.
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "test-only-jwt-secret-key-at-least-32-bytes"
    )

    import database

    # Redirect every database operation to a temporary file.
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    # Import the Flask application after configuring the environment.
    app_module = importlib.import_module("app")
    app = app_module.app
    app.config["TESTING"] = True

    # Each test gets freshly created, empty tables.
    database.initialize_database()

    # Flask provides a client that simulates HTTP requests.
    with app.test_client() as test_client:
        yield test_client
