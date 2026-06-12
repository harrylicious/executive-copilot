"""FastAPI application entry point for the Knowledge Base Manager."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import ingestion_settings, settings, turbovec_settings
from app.database import Base, engine
from app.models import (  # noqa: F401 - register models
    File,
    SyncLog,
    Chunk,
    EmbeddingLog,
    ChatSession,
    ChatMessageRecord,
    IngestionJob,
    IngestionStageLog,
    BatchLoaderConfig,
    BatchExecutionLog,
    PIIRedactionLog,
    FileRelationship,
    User,
    UserSettings,
    ChatFeedback,
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

    # Log TurboVec configuration at startup
    logger.info(
        "TurboVec settings loaded: embedding_model=%s, chunk_size=%d, "
        "chunk_overlap=%d",
        turbovec_settings.embedding_model,
        turbovec_settings.chunk_size,
        turbovec_settings.chunk_overlap,
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

    # Store turbovec_settings in app state for access by routers/services
    app.state.turbovec_settings = turbovec_settings

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

    try:
        from app.database import SessionLocal
        from app.services.embedding_engine import EmbeddingEngine

        db = SessionLocal()
        try:
            embedding_engine = EmbeddingEngine(db, turbovec_settings, settings.knowledge_base_path)
            result = embedding_engine.run_full()
            logger.info(
                "Startup full re-embedding completed: files=%d, chunks=%d, errors=%d, status=%s",
                result.files_processed,
                result.chunks_generated,
                len(result.errors),
                result.status,
            )
            if result.errors:
                for err in result.errors[:5]:
                    logger.warning("Embedding error: file_id=%s error=%s", err.get("file_id"), err.get("error"))
        finally:
            db.close()
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("Initial embedding failed (non-fatal): %s", exc)

    # -------------------------------------------------------------------------
    # TurboVec index initialization
    # Load from cache if both .tv files exist; build from scratch if missing.
    # Handle corrupted cache (log warning, discard, rebuild).
    # Handle empty knowledge base (create empty indexes, save, log warning).
    # -------------------------------------------------------------------------
    from pathlib import Path as _Path

    from app.services.embedding_model import EmbeddingModel
    from app.services.retrieval_dependencies import set_store
    from app.services.turbovec_store import TurboVecStore
    from turbovec.langchain import TurboQuantVectorStore

    embedding_model = EmbeddingModel(turbovec_settings.embedding_model)
    store = TurboVecStore(turbovec_settings, embedding_model)

    cache_dir = _Path(turbovec_settings.index_cache_dir)
    master_cache = cache_dir / "master"
    dept_cache = cache_dir / "dept"

    indexes_ready = False

    # Attempt to load both indexes from cache
    if master_cache.exists() and dept_cache.exists():
        try:
            loaded = store.load_from_cache()
            if loaded:
                logger.info("TurboVec indexes loaded from cache successfully")
                indexes_ready = True
            else:
                # load_from_cache returned False — one or both failed internally
                logger.warning(
                    "TurboVec cache load returned False; will rebuild indexes"
                )
        except Exception as exc:
            logger.warning(
                "TurboVec cache is corrupted or incompatible: %s. "
                "Discarding cache and rebuilding indexes.",
                exc,
            )
            # Discard corrupted cache directories
            import shutil as _shutil
            try:
                if master_cache.exists():
                    _shutil.rmtree(master_cache)
                if dept_cache.exists():
                    _shutil.rmtree(dept_cache)
            except OSError as rm_err:
                logger.warning("Failed to remove corrupted cache directories: %s", rm_err)

    # Build from scratch if cache was missing, corrupted, or failed to load
    if not indexes_ready:
        try:
            store.build_indexes(settings.knowledge_base_path)
            store.save_to_cache()
            logger.info(
                "TurboVec indexes built from knowledge base and saved to cache"
            )
            indexes_ready = True
        except ValueError as ve:
            # Empty knowledge base — create empty indexes, save, log warning
            if "Empty knowledge base" in str(ve) or "no supported documents" in str(ve):
                logger.warning(
                    "Knowledge base contains no documents: %s. "
                    "Creating empty TurboVec indexes.",
                    ve,
                )
                store.master_index = TurboQuantVectorStore(
                    embedding=store._lc_embedding,
                    bit_width=4,
                )
                store.dept_index = TurboQuantVectorStore(
                    embedding=store._lc_embedding,
                    bit_width=4,
                )
                store.save_to_cache()
                logger.warning(
                    "Empty TurboVec indexes created and saved to cache. "
                    "No documents were indexed."
                )
                indexes_ready = True
            else:
                # Non-empty-KB ValueError (e.g. path doesn't exist) — re-raise
                raise
        except Exception as exc:
            logger.error("Failed to build TurboVec indexes: %s", exc)
            raise

    # Inject the fully-initialized store into the global retrieval dependencies
    set_store(store)
    logger.info("TurboVec store injected into retrieval dependencies")

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
    from app.routers.transform import router as transform_router

    app.include_router(transform_router, prefix="/api")
except ImportError:
    pass  # transform router not yet implemented

try:
    from app.routers.feedback import router as feedback_router

    app.include_router(feedback_router, prefix="/api")
except ImportError:
    pass  # feedback router not yet implemented

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

try:
    from app.routers.dashboard import router as dashboard_router

    app.include_router(dashboard_router, prefix="/api")
except ImportError:
    pass  # dashboard router not yet implemented

try:
    from app.routers.graph import router as graph_router

    app.include_router(graph_router, prefix="/api")
except ImportError:
    pass  # graph router not yet implemented

try:
    from app.routers.users import router as users_router

    app.include_router(users_router, prefix="/api")
except ImportError:
    pass  # users router not yet implemented

try:
    from app.routers.settings import router as settings_router

    app.include_router(settings_router, prefix="/api")
except ImportError:
    pass  # settings router not yet implemented

try:
    from app.routers.auth import router as auth_router

    app.include_router(auth_router, prefix="/api")
except ImportError:
    pass  # auth router not yet implemented
