from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.core.database import engine, Base
import app.models  # ensure models are registered
from app.api.auth import router as auth_router
from app.api.teams import router as teams_router
from app.api.work_items import router as work_items_router

# Note: Schema is managed via Alembic migrations, do not call create_all here.

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Operations Under Pressure — Internal Operations Management API",
    version="1.0.0",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom structured error responses
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": str(exc.detail)
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Sanitize validation error details:
    - Never echo submitted input (e.g. passwords).
    - Ensure 'ctx' values are JSON-serializable strings.
    """
    sanitized_errors = []
    for err in exc.errors():
        clean_err = {
            "type": err.get("type"),
            "loc": err.get("loc"),
            "msg": err.get("msg"),
        }
        if "ctx" in err and isinstance(err["ctx"], dict):
            clean_err["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        sanitized_errors.append(clean_err)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request parameters.",
            "detail": sanitized_errors
        }
    )

@app.get("/")
def root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "operational",
        "docs_url": "/docs"
    }

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

# Mount API routers
app.include_router(auth_router, prefix="/api")
app.include_router(teams_router, prefix="/api")
app.include_router(work_items_router, prefix="/api")
