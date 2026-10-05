import sys
import asyncio
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.config import settings
from backend.api.routes import router as api_router
from backend.api.sse import sse_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set running event loop for thread-safe SSE dispatch
    loop = asyncio.get_running_loop()
    sse_manager.set_loop(loop)
    print(f"FinSight Research Intelligence Engine active on port {settings.BACKEND_PORT}")
    yield

app = FastAPI(
    title="FinSight Financial Research Intelligence API",
    version="1.0.0",
    description="Agentic multi-agent financial research system featuring iterative RAG, targeted replanning, and human-in-the-loop review.",
    lifespan=lifespan
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "FinSight Backend",
        "version": "1.0.0",
        "chroma_dir": settings.CHROMA_PERSIST_DIR,
        "gemini_model": settings.GEMINI_MODEL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=settings.BACKEND_PORT, reload=True)
