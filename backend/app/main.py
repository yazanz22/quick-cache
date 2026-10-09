import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT
from .routes import llm_routes, sim_routes

log = logging.getLogger("nas")


def _warm_up_in_background() -> None:
    """Pre-compute the demo path (fast first requests after a cold start). A failure is logged, never fatal."""
    try:
        secs = sim_routes.warm_up()
        log.info("demo path warmed in %.1fs", secs)
    except Exception:
        log.exception("start-up warm-up failed; the server keeps running and computes everything live")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # In a daemon thread, so /health and the UI answer at once after a cold start; requests that arrive
    # before it finishes simply compute live.
    threading.Thread(target=_warm_up_in_background, name="nas-warmup", daemon=True).start()
    yield


app = FastAPI(title="Nas API", lifespan=lifespan)

# Only needed if the frontend is served from another port (e.g. python -m http.server 3000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# /population and /compare are ~0.5-1 MB of JSON; gzip makes them several times smaller on the wire.
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.exception_handler(RequestValidationError)
async def _validation_error(_request: Request, exc: RequestValidationError):
    """A clean 422 for a malformed body. FastAPI's default handler echoes the input back, which fails to
    serialise (500) when the body holds NaN or Infinity."""
    detail = [{"loc": list(e.get("loc", ())), "msg": str(e.get("msg", "")), "type": str(e.get("type", ""))}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


app.include_router(sim_routes.router)
app.include_router(llm_routes.router)


@app.get("/health")
def health():
    return {"ok": True, "warm": sim_routes.WARM_DONE.is_set()}


# The frontend, served by the same server: http://localhost:8000/ . Mounted last so API routes win.
app.mount("/", StaticFiles(directory=REPO_ROOT / "nas-frontend", html=True), name="frontend")
