"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.database import init_db
from app.services.graph_manager import graph_manager

from app.routers import projects, datasources, ontology, graph, qa, dashboard, system


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Startup
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    # Ensure data directory for SQLite
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    await init_db()
    yield
    # Shutdown
    await graph_manager.close()


app = FastAPI(
    title="Auto Ontology Builder & QA System",
    description="Automatic ontology construction and intelligent Q&A based on knowledge graph + LLM",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(projects.router)
app.include_router(datasources.router)
app.include_router(ontology.router)
app.include_router(graph.router)
app.include_router(qa.router)
app.include_router(dashboard.router)
app.include_router(system.router)


@app.get("/")
async def root():
    return {
        "name": "Auto Ontology Builder & QA System",
        "version": "1.0.0",
        "docs": "/docs",
    }
