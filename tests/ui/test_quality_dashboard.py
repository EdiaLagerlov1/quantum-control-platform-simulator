"""Browser tests: does the quality dashboard show what it should?

The SQL behind every panel was already checked through Grafana's API. That did not catch a chart
that rendered as an empty box. Only a real browser sees what a person sees.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.ui

CHART_TYPES = {"timeseries", "barchart"}


def panel(page: Page, title: str) -> Locator:
    """Find a panel by its title. Grafana marks every panel with a test id built from it."""
    return page.get_by_test_id(f"data-testid Panel header {title}")


def test_every_panel_renders_its_data(dashboard: Page, panels: list[dict[str, Any]]) -> None:
    for definition in panels:
        title = definition["title"]
        box = panel(dashboard, title)

        expect(box, f"panel {title!r} is missing").to_be_visible()
        expect(box, f"panel {title!r} has no data").not_to_contain_text("No data")
        if definition["type"] in CHART_TYPES:
            # A chart draws on a <canvas>. No canvas means an empty box, even with good data.
            expect(box.locator("canvas"), f"chart {title!r} was not drawn").to_have_count(1)


def test_release_readiness_shows_main_passing(dashboard: Page) -> None:
    expect(panel(dashboard, "CI on main")).to_contain_text("PASS")
    expect(panel(dashboard, "Open High/Critical bugs")).to_contain_text("0")


def test_failures_table_explains_the_red_run(dashboard: Page) -> None:
    failures = panel(dashboard, "Failures")

    # A developer must see which test broke and why, without opening the CI log.
    expect(failures).to_contain_text("test_valid_request_creates_experiment")
    expect(failures).to_contain_text("assert 201 == 203")
