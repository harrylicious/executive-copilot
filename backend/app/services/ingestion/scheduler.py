"""Batch Scheduler for managing cron-based batch loader executions.

Uses APScheduler with a SQLite job store for persistent scheduling.
Handles the case where APScheduler is not installed gracefully by
logging a warning and disabling scheduling functionality.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Attempt to import APScheduler; gracefully degrade if not installed.
try:
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning(
        "APScheduler is not installed. Batch scheduling functionality is disabled. "
        "Install with: pip install apscheduler"
    )

# Regex pattern for valid S3 URIs: s3://bucket-name/optional-prefix
_S3_URI_PATTERN = re.compile(
    r"^s3://[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]"  # bucket name
    r"(/[^\s]*)?$"  # optional prefix
)


class BatchScheduler:
    """Manage cron-based scheduling of batch loader executions.

    Uses APScheduler with a SQLite job store derived from the project's
    database configuration. If APScheduler is not installed, all scheduling
    methods log warnings and return gracefully without raising errors.
    """

    def __init__(self) -> None:
        """Initialize the BatchScheduler.

        Sets up the APScheduler BackgroundScheduler with a SQLAlchemy job store
        using the project's configured SQLite database URL.
        """
        self._scheduler = None
        self._started = False

        if not APSCHEDULER_AVAILABLE:
            return

        # Derive the SQLite database path from the project's database_url
        db_url = settings.database_url
        jobstores = {
            "default": SQLAlchemyJobStore(url=db_url),
        }
        self._scheduler = BackgroundScheduler(jobstores=jobstores)

    def start(self) -> None:
        """Initialize and start the scheduler.

        If APScheduler is not available or the scheduler is already running,
        this method is a no-op (with a warning logged for the former case).
        """
        if not APSCHEDULER_AVAILABLE:
            logger.warning(
                "Cannot start scheduler: APScheduler is not installed."
            )
            return

        if self._started:
            logger.debug("Scheduler is already running.")
            return

        self._scheduler.start()
        self._started = True
        logger.info("BatchScheduler started successfully.")

    def add_schedule(self, config) -> str | None:
        """Add a cron-based job that triggers the batch loader's execute_scan.

        Parses the cron_expression from the config and schedules a job
        that will call the batch loader's execute_scan with the config's ID.

        Args:
            config: A BatchLoaderConfig instance (or object with id,
                    cron_expression, and name attributes).

        Returns:
            The job ID string if successfully scheduled, or None if
            scheduling is unavailable.
        """
        if not APSCHEDULER_AVAILABLE:
            logger.warning(
                "Cannot add schedule: APScheduler is not installed."
            )
            return None

        if not self._started:
            logger.warning(
                "Cannot add schedule: scheduler has not been started. "
                "Call start() first."
            )
            return None

        # Parse cron expression (expects 5-field format: min hour day month dow)
        cron_parts = config.cron_expression.strip().split()
        if len(cron_parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{config.cron_expression}': "
                f"expected 5 fields (minute hour day month day_of_week), "
                f"got {len(cron_parts)}."
            )

        minute, hour, day, month, day_of_week = cron_parts

        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )

        job_id = f"batch_loader_{config.id}"

        # Import batch_loader lazily to avoid circular imports
        from app.services.ingestion.batch_loader import BatchLoader

        # Add or replace the job
        self._scheduler.add_job(
            func=BatchLoader.execute_scan,
            trigger=trigger,
            id=job_id,
            name=f"Batch scan: {config.name}",
            args=[BatchLoader(), config.id],
            replace_existing=True,
        )

        logger.info(
            f"Scheduled batch job '{job_id}' with cron '{config.cron_expression}'."
        )
        return job_id

    def remove_schedule(self, config_id: str) -> None:
        """Remove a scheduled job by config ID.

        Args:
            config_id: The BatchLoaderConfig ID whose schedule should be removed.
        """
        if not APSCHEDULER_AVAILABLE:
            logger.warning(
                "Cannot remove schedule: APScheduler is not installed."
            )
            return

        if not self._started:
            logger.warning(
                "Cannot remove schedule: scheduler has not been started."
            )
            return

        job_id = f"batch_loader_{config_id}"
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job '{job_id}'.")
        except Exception as e:
            logger.warning(f"Could not remove job '{job_id}': {e}")

    def get_next_run(self, config_id: str) -> datetime | None:
        """Return the next scheduled execution time for a config.

        Args:
            config_id: The BatchLoaderConfig ID to query.

        Returns:
            The next run datetime, or None if the job is not found
            or scheduling is unavailable.
        """
        if not APSCHEDULER_AVAILABLE:
            logger.warning(
                "Cannot get next run: APScheduler is not installed."
            )
            return None

        if not self._started:
            return None

        job_id = f"batch_loader_{config_id}"
        job = self._scheduler.get_job(job_id)
        if job is None:
            return None

        return job.next_run_time

    @staticmethod
    def configure(source_path: str) -> None:
        """Validate that the source path is a valid local path or S3 URI.

        A valid source path is either:
        - A local filesystem path (absolute path that could exist on the system)
        - An S3 URI matching the pattern s3://bucket-name/optional-prefix

        Args:
            source_path: The source path string to validate.

        Raises:
            ValueError: If the source path is neither a valid local path
                        nor a valid S3 URI.
        """
        if not source_path or not source_path.strip():
            raise ValueError(
                "Source path cannot be empty."
            )

        source_path = source_path.strip()

        # Check if it's a valid S3 URI
        if source_path.startswith("s3://"):
            if _S3_URI_PATTERN.match(source_path):
                return
            raise ValueError(
                f"Invalid S3 URI '{source_path}'. "
                f"Expected format: s3://bucket-name/optional-prefix"
            )

        # Check if it's a valid local filesystem path
        # A valid local path should be an absolute path.
        # We accept both Unix-style (starts with /) and Windows-style
        # (e.g., C:\, D:\) absolute paths regardless of the current platform.
        if source_path.startswith("/"):
            # Unix absolute path
            return

        try:
            path = Path(source_path)
            if path.is_absolute():
                return
        except (OSError, ValueError):
            pass

        raise ValueError(
            f"Invalid source path '{source_path}'. "
            f"Must be an absolute local filesystem path or an S3 URI "
            f"(s3://bucket-name/prefix)."
        )

    def shutdown(self) -> None:
        """Shut down the scheduler gracefully."""
        if not APSCHEDULER_AVAILABLE:
            return

        if self._started and self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("BatchScheduler shut down.")
