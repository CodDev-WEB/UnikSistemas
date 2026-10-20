from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import get_db
from app.routes import router

settings = get_settings()

app = FastAPI(
    title="UnikSistemas API",
    description=(
        "Fundação inicial do SaaS contábil: provisionamento controlado, autenticação "
        "e cadastro de clientes com isolamento por escritório."
    ),
    version="0.1.0",
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Bootstrap-Token"],
    )

app.include_router(router)


@app.get("/", tags=["System"])
def root():
    return {"name": "UnikSistemas API", "version": app.version, "docs": "/docs"}


@app.get("/health/live", tags=["System"])
def health_live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["System"])
def health_ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.") from None
    return {"status": "ready", "database": "ok"}
