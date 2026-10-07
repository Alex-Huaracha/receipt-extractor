from fastapi import FastAPI

from app.api.routes import health

app = FastAPI(title="Receipt Extractor")

app.include_router(health.router)
