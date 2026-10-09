from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT
from .routes import llm_routes, sim_routes


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sim_routes.warm_up()  # demo path pre-computed before the first request (fast after cold starts)
    yield


app = FastAPI(title="Nas API", lifespan=lifespan)

# Only needed if the frontend is served from another port (e.g. python -m http.server 3000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sim_routes.router)
app.include_router(llm_routes.router)


@app.get("/health")
def health():
    return {"ok": True}


# The frontend, served by the same server: http://localhost:8000/ . Mounted last so API routes win.
app.mount("/", StaticFiles(directory=REPO_ROOT / "nas-frontend", html=True), name="frontend")
