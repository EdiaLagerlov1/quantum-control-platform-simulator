import definition from "../../../observability/grafana/dashboards/quality.json";
import { expect, test } from "../fixtures";

// The same three checks as tests/ui (Python) and tests/cypress, now with page objects.

const CHART_TYPES = new Set(["timeseries", "barchart"]);
const panels = definition.panels.filter((p) => p.type !== "row");

test.describe("Quality dashboard", () => {
  // One test per panel, generated from the dashboard definition in git:
  // a failure names the broken panel, and the others still run.
  for (const { title, type } of panels) {
    test(`panel "${title}" renders its data`, async ({ dashboard }) => {
      const panel = dashboard.panel(title);
      await panel.expectToShowData();
      if (CHART_TYPES.has(type)) await panel.expectChartDrawn();
    });
  }

  test("release readiness shows main passing", async ({ dashboard }) => {
    await expect(dashboard.ciOnMain.root).toContainText("PASS");
    await expect(dashboard.openHighCriticalBugs.root).toContainText("0");
  });

  test("failures table explains the red run", async ({ dashboard }) => {
    // A developer must see which test broke and why, without opening the CI log.
    await expect(dashboard.failures.root).toContainText("test_valid_request_creates_experiment");
    await expect(dashboard.failures.root).toContainText("assert 201 == 203");
  });
});
