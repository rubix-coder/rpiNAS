"""FastAPI application entry point with GPU worker lifespan."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import engine, init_db
from .models.scorer import AestheticScorer
from .routers import albums, decisions, export, images, settings
from .services.scoring_service import scoring_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()

    # Ensure DB and data directories exist
    Path(cfg.db_path).parent.mkdir(parents=True, exist_ok=True)
    await init_db()
    logger.info("Database initialised at %s", cfg.db_path)

    # Load CLIP model off the main thread
    scorer = AestheticScorer(
        device=cfg.device,
        model_name=cfg.clip_model,
        pretrained=cfg.clip_pretrained,
        weights_path=cfg.aesthetic_predictor_weights,
    )
    loop = asyncio.get_event_loop()
    try:
        logger.info("Loading CLIP model (%s / %s) on %s …", cfg.clip_model, cfg.clip_pretrained, cfg.device)
        await loop.run_in_executor(None, scorer.load)
        logger.info("CLIP model loaded successfully")
    except Exception as e:
        logger.warning("Could not load CLIP model (%s) — scoring will be disabled", e)

    # Shared queue between scan router and scoring worker
    score_queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
    app.state.score_queue = score_queue
    app.state.scorer = scorer

    # Start background scoring worker
    worker_task = asyncio.create_task(
        scoring_worker(score_queue, scorer, cfg, engine),
        name="scoring_worker",
    )
    logger.info("Scoring worker started")

    yield

    # Shutdown
    logger.info("Shutting down scoring worker …")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Photo Curator",
    description="GPU-accelerated photo curation for physical album printing",
    version="1.0.0",
    lifespan=lifespan,
)

# API routers
app.include_router(images.router)
app.include_router(decisions.router)
app.include_router(albums.router)
app.include_router(export.router)
app.include_router(settings.router)


@app.get("/api/health")
async def health():
    cfg = get_settings()
    scorer: AestheticScorer = app.state.scorer if hasattr(app.state, "scorer") else None
    return {
        "status": "ok",
        "device": cfg.device,
        "model_loaded": scorer.is_loaded if scorer else False,
    }


# Mount frontend static files
_frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")

    @app.get("/")
    async def serve_spa():
        return FileResponse(str(_frontend_dir / "index.html"))

    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        # Serve index.html for any non-API path (SPA routing)
        candidate = _frontend_dir / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_frontend_dir / "index.html"))
