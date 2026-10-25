from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from clearledger.api import router
from clearledger.case_api import router as case_router
from clearledger.config import Settings
from clearledger.db import build_engine, get_session
from clearledger.document_api import router as document_router
from clearledger.evidence_api import router as evidence_router
from clearledger.extraction_provider import Gateway, GeminiTransport
from clearledger.finance_api import router as finance_router
from clearledger.investigation_api import router as investigation_router
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
    # A trusted host must supply a verified identity adapter. Local tokens/labels do not qualify.
    app.state.finance_identity_verifier = None
    app.state.extraction_gateway = None
    if (
        config.extraction_provider == "gemini"
        and config.external_ai_enabled
        and config.privacy_review_reference
        and config.gemini_api_key
        and config.gemini_model
    ):
        app.state.extraction_gateway = Gateway(
            GeminiTransport(
                config.gemini_api_key.get_secret_value(),
                config.gemini_model,
                config.llm_timeout_ms,
                max_input_tokens=config.llm_max_input_tokens,
                max_output_tokens=config.llm_max_output_tokens,
            ),
            attempts=config.llm_attempts,
            requests_per_minute=config.llm_requests_per_minute,
            input_rate=config.llm_input_paise_per_million_tokens,
            output_rate=config.llm_output_paise_per_million_tokens,
            max_input_tokens=config.llm_max_input_tokens,
            max_output_tokens=config.llm_max_output_tokens,
        )
    app.include_router(router)
    app.include_router(matching_router)
    app.include_router(document_router)
    app.include_router(case_router)
    app.include_router(evidence_router)
    app.include_router(finance_router)
    app.include_router(investigation_router)

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
