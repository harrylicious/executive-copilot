"""FastAPI application entry point for the Knowledge Base Manager."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import graphrag_settings, ingestion_settings, settings
from app.database import Base, engine
from app.models import (  # noqa: F401 - register models
    File,
    Relationship,
    SyncLog,
    Chunk,
    Entity,
    EntityRelationship,
    Community,
    EmbeddingLog,
    ChatSession,
    ChatMessageRecord,
    IngestionJob,
    IngestionStageLog,
    BatchLoaderConfig,
    BatchExecutionLog,
    PIIRedactionLog,
)
from app.utils.department_config import initialize_knowledge_base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: runs startup logic before serving requests."""
    # Create all database tables (additive — preserves existing tables and data)
    Base.metadata.create_all(bind=engine)

    # Migrate existing tables: add missing columns to files table
    inspector = inspect(engine)
    if "files" in inspector.get_table_names():
        file_columns = [c["name"] for c in inspector.get_columns("files")]
        migrations = {
            "embedding_status": "ALTER TABLE files ADD COLUMN embedding_status VARCHAR",
            "subfolder": "ALTER TABLE files ADD COLUMN subfolder VARCHAR",
            "file_type": "ALTER TABLE files ADD COLUMN file_type VARCHAR",
            "sync_status": "ALTER TABLE files ADD COLUMN sync_status VARCHAR DEFAULT 'synced'",
            "checksum_md5": "ALTER TABLE files ADD COLUMN checksum_md5 VARCHAR",
            "extracted_text": "ALTER TABLE files ADD COLUMN extracted_text TEXT",
            "sensitivity_level": "ALTER TABLE files ADD COLUMN sensitivity_level VARCHAR DEFAULT 'Internal'",
            "is_deleted": "ALTER TABLE files ADD COLUMN is_deleted BOOLEAN DEFAULT 0",
            "indexed_at": "ALTER TABLE files ADD COLUMN indexed_at DATETIME",
        }
        for col_name, alter_sql in migrations.items():
            if col_name not in file_columns:
                with engine.connect() as conn:
                    conn.execute(text(alter_sql))
                    conn.commit()
                logger.info(f"Added {col_name} column to files table")

    # Migrate existing tables: add missing columns to chunks table
    if "chunks" in inspector.get_table_names():
        chunk_columns = [c["name"] for c in inspector.get_columns("chunks")]
        chunk_migrations = {
            "section_path": "ALTER TABLE chunks ADD COLUMN section_path VARCHAR",
            "chunking_method": "ALTER TABLE chunks ADD COLUMN chunking_method VARCHAR",
            "job_id": "ALTER TABLE chunks ADD COLUMN job_id VARCHAR REFERENCES ingestion_jobs(id)",
        }
        for col_name, alter_sql in chunk_migrations.items():
            if col_name not in chunk_columns:
                with engine.connect() as conn:
                    conn.execute(text(alter_sql))
                    conn.commit()
                logger.info(f"Added {col_name} column to chunks table")

    # Create staging directory for ingestion pipeline
    from pathlib import Path

    staging_path = Path(ingestion_settings.staging_path)
    staging_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Staging directory ensured at: {staging_path.resolve()}")

    # Log GraphRAG configuration at startup
    logger.info(
        "GraphRAG settings loaded: embedding_model=%s, chunk_size=%d, "
        "chunk_overlap=%d, entity_extraction_method=%s",
        graphrag_settings.embedding_model,
        graphrag_settings.chunk_size,
        graphrag_settings.chunk_overlap,
        graphrag_settings.entity_extraction_method,
    )

    # Log LangChain package availability and LLM configuration status
    try:
        from app.services.langchain import LANGCHAIN_AVAILABLE
        from app.services.langchain.config import LangChainSettings

        if LANGCHAIN_AVAILABLE:
            logger.info("LangChain packages are available; LLM features enabled.")
        else:
            logger.warning(
                "LangChain packages are not available; LLM features disabled. "
                "Retrieval endpoints remain operational."
            )

        langchain_settings = LangChainSettings()
        if langchain_settings.is_llm_configured():
            logger.info(
                "LLM provider configured: provider=%s, model=%s",
                langchain_settings.llm_provider,
                langchain_settings.llm_model,
            )
        else:
            logger.warning(
                "LLM provider is not configured (KB_LLM_PROVIDER and/or KB_LLM_API_KEY missing). "
                "Chat endpoints will return 503 until configured."
            )
    except Exception as exc:
        logger.warning(
            "Failed to check LangChain configuration at startup: %s. "
            "LLM features may be unavailable.",
            exc,
        )

    # Store graphrag_settings in app state for access by routers/services
    app.state.graphrag_settings = graphrag_settings

    # Initialize knowledge base folder structure
    initialize_knowledge_base(settings.knowledge_base_path)

    # Initialize LangChain service container (logs status at startup)
    try:
        from app.services.langchain.dependencies import get_service_container

        container = get_service_container()
        if container.is_llm_available:
            logger.info(
                "LangChain LLM features are enabled: provider=%s, model=%s",
                container.settings.llm_provider,
                container.settings.llm_model,
            )
        else:
            logger.info(
                "LangChain LLM features are disabled. "
                "Existing retrieval endpoints remain operational."
            )
    except Exception as exc:
        logger.warning(f"LangChain service container initialization failed: {exc}")

    # Seed sample data (skip if files already exist)
    try:
        from app.services.seed_service import seed_knowledge_base

        seed_knowledge_base(settings.knowledge_base_path)
    except ImportError:
        pass  # seed_service not yet implemented

    # Run initial sync to index any existing files
    try:
        from app.database import SessionLocal
        from app.services.sync_engine import SyncEngine

        db = SessionLocal()
        try:
            sync_engine = SyncEngine(db, settings.knowledge_base_path)
            sync_engine.execute_sync()
        finally:
            db.close()
    except ImportError:
        pass  # sync_engine not yet implemented

    yield


app = FastAPI(
    title="Knowledge Base Manager",
    description="API for organizing, viewing, and exploring departmental documents.",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with /api prefix
try:
    from app.routers.files import router as files_router

    app.include_router(files_router, prefix="/api")
except ImportError:
    pass  # files router not yet implemented

try:
    from app.routers.departments import router as departments_router

    app.include_router(departments_router, prefix="/api")
except ImportError:
    pass  # departments router not yet implemented

try:
    from app.routers.sync import router as sync_router

    app.include_router(sync_router, prefix="/api")
except ImportError:
    pass  # sync router not yet implemented

try:
    from app.routers.graph import router as graph_router

    app.include_router(graph_router, prefix="/api")
except ImportError:
    pass  # graph router not yet implemented

try:
    from app.routers.embeddings import router as embeddings_router

    app.include_router(embeddings_router, prefix="/api")
except ImportError:
    pass  # embeddings router not yet implemented

try:
    from app.routers.search import router as search_router

    app.include_router(search_router, prefix="/api")
except ImportError:
    pass  # search router not yet implemented

try:
    from app.routers.chat import router as chat_router

    app.include_router(chat_router, prefix="/api")
except ImportError:
    pass  # chat router not yet implemented

try:
    from app.routers.sessions import router as sessions_router

    app.include_router(sessions_router, prefix="/api")
except ImportError:
    pass  # sessions router not yet implemented

try:
    from app.routers.ingestion import router as ingestion_router

    app.include_router(ingestion_router, prefix="/api")
except ImportError:
    pass  # ingestion router not yet implemented
