# this file initializes the fastAPI application, sets up middleware rules,
# and mounts the sub-routing endpoints to expose our web services

# Application Entry Point: Boots the web framework, runs the programmatic 
# database migration engine initialization, and handles CORS parameters.

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine, Base
from app.api.routes import router as api_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Persistent Sales Agent API",
    description="Production-grade multi-turn conversational sales B2B agent backend featuring native context memory evaluation loops.",
    version="2026.1.0"
)

# (CORS) security parameters
# This ensures a React, Vue, or Next.js frontend can query this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits requests from any origin domain. Tighten this for true production deployments.
    allow_credentials=True,
    allow_methods=["*"],  # Permits standard HTTP verbs (GET, POST, DELETE, OPTIONS)
    allow_headers=["*"],  # Permits downstream custom network header packages
)

# Mount isolated endpoint routing tier directly to the application root
app.include_router(api_router)

# root route landing index configuration to prevent default 404 errors on root address
@app.get("/", tags=["Root"])
def read_root_index():
    """
    Landing page redirect payload providing core server configuration metadata.
    """
    return {
        "service": "SaaSify Sales Assistant Agent Engine",
        "status": "online",
        "documentation_docs": "/docs",
        "documentation_redoc": "/redoc"
    }