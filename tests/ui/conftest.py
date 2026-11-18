"""Fixtures for the browser tests of the quality dashboard.

pytest-playwright provides the ``page`` fixture: a fresh browser tab for every test. These tests
need the dashboard running (see README, "Quality dashboard"), so they are not part of the default
run. Run them with: uv run pytest -m ui
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_JSON = ROOT / "observability" / "grafana" / "dashboards" / "quality.json"
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def panels() -> list[dict[str, Any]]:
    """The panels as defined in git. The tests check that each of them actually renders."""
    definition = json.loads(DASHBOARD_JSON.read_text())
    return [panel for panel in definition["panels"] if panel["type"] != "row"]


@pytest.fixture
def dashboard(page: Page) -> Page:
    """A browser tab with the dashboard open and its first panel on screen."""
    page.set_viewport_size({"width": 1600, "height": 2000})  # tall: every panel is rendered
    page.goto(f"{GRAFANA_URL}/d/quality?orgId=1&from=now-7d&to=now")
    page.get_by_test_id("data-testid Panel header CI on main").wait_for()
    return page
