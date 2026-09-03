import sys
from pathlib import Path

# Ensure project root is in sys.path so it works when executed from any directory
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
try:
    from Phase_4.routers.network import router as network_router
except ModuleNotFoundError:
    from routers.network import router as network_router

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Trigger model loading
    try:
        from Phase_4 import ml5_model_service
        # Accessing MODEL verifies it loaded successfully
        _ = ml5_model_service.MODEL
    except ModuleNotFoundError:
        import ml5_model_service
        _ = ml5_model_service.MODEL
    yield

app = FastAPI(
    title="NOPIS Phase 4 — Network Operations Predictive Intelligence System API",
    description="REST API for querying analytics metrics and network summaries from the telecom warehouse.",
    version="1.0.0",
    lifespan=lifespan
)

# 162. Configure CORS on FastAPI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(network_router)

@app.get("/")
def root():
    return {
        "message": "NOPIS Network Summary API is running.",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, app_dir=str(Path(__file__).resolve().parent))
