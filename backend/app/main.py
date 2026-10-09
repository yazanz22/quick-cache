from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .routes import llm_routes, sim_routes

app = FastAPI(title="Nas API")

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


@app.get("/", include_in_schema=False)
def debug_page():
    """Plain HTML page for poking at the API. The real UI lives in frontend/."""
    return FileResponse(Path(__file__).parent / "static" / "debug.html")
