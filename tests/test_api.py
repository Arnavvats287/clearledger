from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from clearledger.config import Settings
from clearledger.db import get_session
from clearledger.main import create_app


def test_health_does_not_connect_to_database():
    app = create_app(Settings(database_url="postgresql+psycopg://unused@127.0.0.1:1/unused"))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/health").status_code == 200


def test_ready_failure_is_503_and_redacted():
    app = create_app(Settings(database_url="postgresql+psycopg://unused@127.0.0.1:1/unused"))
    session = Mock()
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("secret-password"))
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
        assert "secret-password" not in response.text


def test_non_postgresql_configuration_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///substitute.db")
