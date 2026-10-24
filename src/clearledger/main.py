from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from clearledger.api import router
from clearledger.config import Settings
from clearledger.db import build_engine, get_session
from clearledger.matching_api import router as matching_router


class HealthResponse(BaseModel):
    status: Literal["ok", "ready"]


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = build_engine(config.database_url)
        app.state.session_factory = sessionmaker(engine)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="ClearLedger", version="0.1.0", lifespan=lifespan)
    app.state.settings = config
    app.include_router(router)
    app.include_router(matching_router)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/ready", response_model=HealthResponse)
    def ready(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="Database unavailable") from None
        return HealthResponse(status="ready")

    return app
