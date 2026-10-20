from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import editorial, public
from app.config import get_settings
from app.db import get_engine


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Przepisy budowlane — API",
        version="0.1.0",
        description=(
            "Publiczne API przepisów budowlanych: oficjalny tekst z jawnym typem i stanem prawnym, "
            "status aktualności, objaśnienia nieurzędowe, kreator, ścieżki i słowniczek. "
            "Informacja, nie porada prawna."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(public.router)
    app.include_router(editorial.router)

    @app.get("/healthz", tags=["operacje"])
    def healthz() -> dict[str, str]:
        with get_engine().connect() as conn:
            conn.execute(text("select 1"))
        return {"status": "ok"}

    return app


app = create_app()
