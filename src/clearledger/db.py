from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def build_engine(database_url: str):
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3, "options": "-c timezone=UTC"},
    )


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session
