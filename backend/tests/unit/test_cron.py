from datetime import datetime, timezone

import pytest

from app.application.services.cron import cron_matches, next_cron_run, validate_cron_expression


def test_cron_matches_step_expression() -> None:
    assert cron_matches("*/5 * * * *", datetime(2026, 6, 20, 8, 45, tzinfo=timezone.utc))
    assert not cron_matches("*/5 * * * *", datetime(2026, 6, 20, 8, 46, tzinfo=timezone.utc))


def test_next_cron_run_returns_next_matching_minute() -> None:
    next_run = next_cron_run(
        "*/15 * * * *",
        after=datetime(2026, 6, 20, 8, 46, 30, tzinfo=timezone.utc),
    )

    assert next_run == datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc)


def test_cron_rejects_invalid_expression() -> None:
    with pytest.raises(ValueError, match="5 fields"):
        validate_cron_expression("* * *")
