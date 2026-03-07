"""Main app wiring and local run entrypoint."""

import uvicorn
from fastapi import FastAPI

from api import router as api_router
from config import settings
from db import init_db


app = FastAPI(title=settings.APP_NAME)
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.on_event("startup")
def startup() -> None:
    init_db()


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
