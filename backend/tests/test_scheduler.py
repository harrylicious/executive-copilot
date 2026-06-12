"""Unit tests for the BatchScheduler class."""

import pytest

from app.services.ingestion.scheduler import BatchScheduler, _S3_URI_PATTERN


class TestConfigure:
    """Tests for BatchScheduler.configure() source path validation."""

    # --- Valid local paths ---

    def test_valid_absolute_unix_path(self):
        """Absolute Unix-style path should be accepted."""
        BatchScheduler.configure("/home/user/documents")

    def test_valid_absolute_windows_path(self):
        """Absolute Windows-style path should be accepted."""
        BatchScheduler.configure("C:\\Users\\admin\\documents")

    def test_valid_absolute_path_with_trailing_slash(self):
        """Absolute path with trailing slash should be accepted."""
        BatchScheduler.configure("/var/data/ingestion/")

    # --- Valid S3 URIs ---

    def test_valid_s3_uri_with_prefix(self):
        """S3 URI with bucket and prefix should be accepted."""
        BatchScheduler.configure("s3://my-bucket/path/to/files")

    def test_valid_s3_uri_bucket_only(self):
        """S3 URI with bucket only (no prefix) should be accepted."""
        BatchScheduler.configure("s3://my-bucket")

    def test_valid_s3_uri_with_deep_prefix(self):
        """S3 URI with deep prefix path should be accepted."""
        BatchScheduler.configure("s3://company-data-lake/ingestion/2024/q1/docs")

    def test_valid_s3_uri_with_dots_in_bucket(self):
        """S3 URI with dots in bucket name should be accepted."""
        BatchScheduler.configure("s3://my.bucket.name/prefix")

    # --- Invalid paths ---

    def test_empty_string_raises(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            BatchScheduler.configure("")

    def test_whitespace_only_raises(self):
        """Whitespace-only string should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            BatchScheduler.configure("   ")

    def test_relative_path_raises(self):
        """Relative path should raise ValueError."""
        with pytest.raises(ValueError, match="Must be an absolute"):
            BatchScheduler.configure("relative/path/to/files")

    def test_invalid_s3_uri_no_bucket(self):
        """S3 URI without bucket name should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI"):
            BatchScheduler.configure("s3://")

    def test_invalid_s3_uri_short_bucket(self):
        """S3 URI with single-char bucket should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI"):
            BatchScheduler.configure("s3://a/prefix")

    def test_invalid_s3_uri_uppercase_bucket(self):
        """S3 URI with uppercase bucket name should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI"):
            BatchScheduler.configure("s3://MyBucket/prefix")

    def test_plain_text_raises(self):
        """Plain text that is not a path should raise ValueError."""
        with pytest.raises(ValueError, match="Must be an absolute"):
            BatchScheduler.configure("not-a-path")


class TestSchedulerInit:
    """Tests for BatchScheduler initialization and lifecycle."""

    def test_scheduler_creates_without_apscheduler(self, monkeypatch):
        """Scheduler should initialize gracefully even if APScheduler is unavailable."""
        import app.services.ingestion.scheduler as sched_module

        monkeypatch.setattr(sched_module, "APSCHEDULER_AVAILABLE", False)
        scheduler = BatchScheduler()
        # Should not raise, scheduler is None
        assert scheduler._scheduler is None
        assert scheduler._started is False

    def test_start_without_apscheduler_logs_warning(self, monkeypatch, caplog):
        """start() should log a warning when APScheduler is not available."""
        import app.services.ingestion.scheduler as sched_module

        monkeypatch.setattr(sched_module, "APSCHEDULER_AVAILABLE", False)
        scheduler = BatchScheduler()
        scheduler.start()
        assert not scheduler._started

    def test_get_next_run_without_apscheduler(self, monkeypatch):
        """get_next_run() should return None when APScheduler is not available."""
        import app.services.ingestion.scheduler as sched_module

        monkeypatch.setattr(sched_module, "APSCHEDULER_AVAILABLE", False)
        scheduler = BatchScheduler()
        result = scheduler.get_next_run("some-config-id")
        assert result is None

    def test_add_schedule_without_apscheduler(self, monkeypatch):
        """add_schedule() should return None when APScheduler is not available."""
        import app.services.ingestion.scheduler as sched_module

        monkeypatch.setattr(sched_module, "APSCHEDULER_AVAILABLE", False)
        scheduler = BatchScheduler()

        class FakeConfig:
            id = "test-id"
            cron_expression = "0 * * * *"
            name = "Test"

        result = scheduler.add_schedule(FakeConfig())
        assert result is None

    def test_remove_schedule_without_apscheduler(self, monkeypatch):
        """remove_schedule() should not raise when APScheduler is not available."""
        import app.services.ingestion.scheduler as sched_module

        monkeypatch.setattr(sched_module, "APSCHEDULER_AVAILABLE", False)
        scheduler = BatchScheduler()
        # Should not raise
        scheduler.remove_schedule("some-config-id")

    def test_add_schedule_before_start_returns_none(self, monkeypatch):
        """add_schedule() should return None if scheduler hasn't been started."""
        import app.services.ingestion.scheduler as sched_module

        # Keep APSCHEDULER_AVAILABLE True but don't start
        scheduler = BatchScheduler()
        # Don't call start()

        class FakeConfig:
            id = "test-id"
            cron_expression = "0 * * * *"
            name = "Test"

        result = scheduler.add_schedule(FakeConfig())
        assert result is None


class TestCronValidation:
    """Tests for cron expression validation in add_schedule."""

    def test_invalid_cron_too_few_fields(self, monkeypatch):
        """Cron expression with fewer than 5 fields should raise ValueError."""
        import app.services.ingestion.scheduler as sched_module

        # We need APScheduler available and scheduler started for this test
        if not sched_module.APSCHEDULER_AVAILABLE:
            pytest.skip("APScheduler not installed")

        scheduler = BatchScheduler()
        scheduler.start()

        class FakeConfig:
            id = "test-id"
            cron_expression = "0 *"
            name = "Test"

        try:
            with pytest.raises(ValueError, match="expected 5 fields"):
                scheduler.add_schedule(FakeConfig())
        finally:
            scheduler.shutdown()

    def test_invalid_cron_too_many_fields(self, monkeypatch):
        """Cron expression with more than 5 fields should raise ValueError."""
        import app.services.ingestion.scheduler as sched_module

        if not sched_module.APSCHEDULER_AVAILABLE:
            pytest.skip("APScheduler not installed")

        scheduler = BatchScheduler()
        scheduler.start()

        class FakeConfig:
            id = "test-id"
            cron_expression = "0 * * * * *"
            name = "Test"

        try:
            with pytest.raises(ValueError, match="expected 5 fields"):
                scheduler.add_schedule(FakeConfig())
        finally:
            scheduler.shutdown()


class TestS3UriPattern:
    """Tests for the S3 URI regex pattern."""

    def test_valid_bucket_with_prefix(self):
        assert _S3_URI_PATTERN.match("s3://my-bucket/prefix")

    def test_valid_bucket_no_prefix(self):
        assert _S3_URI_PATTERN.match("s3://my-bucket")

    def test_valid_bucket_with_dots(self):
        assert _S3_URI_PATTERN.match("s3://my.bucket.name/path")

    def test_invalid_single_char_bucket(self):
        assert not _S3_URI_PATTERN.match("s3://a/prefix")

    def test_invalid_uppercase_bucket(self):
        assert not _S3_URI_PATTERN.match("s3://MyBucket/prefix")

    def test_invalid_empty_after_scheme(self):
        assert not _S3_URI_PATTERN.match("s3://")
