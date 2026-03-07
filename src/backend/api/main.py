"""Main app wiring and local run entrypoint."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api import router as api_router
from config import settings
from db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize resources once at startup."""
    init_db()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.include_router(api_router, prefix=settings.API_PREFIX)


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
