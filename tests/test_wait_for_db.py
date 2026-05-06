from __future__ import annotations

import pytest


def test_wait_for_db_missing_database_url_is_clear_error():
    from scripts.wait_for_db import wait_for_db

    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        wait_for_db(database_url="", timeout_s=0.1, interval_s=0.01)


def test_wait_for_db_invalid_database_url_is_clear_error():
    from scripts.wait_for_db import wait_for_db

    with pytest.raises(RuntimeError, match="Database not ready"):
        wait_for_db(database_url="not a url", timeout_s=0.1, interval_s=0.01)
