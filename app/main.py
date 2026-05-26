from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router_v1
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup / shutdown フックがあればここに
    yield


app = FastAPI(
    title="おやごころ API",
    description="家族の20年タイムカプセル — バックエンドAPI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router_v1)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "oyagokoro-backend", "version": "0.1.0"}
