import { type Page } from "@playwright/test";
import { Panel } from "./Panel";

/**
 * Page object: the Grafana quality dashboard.
 *
 * Tests talk to this class, never to selectors. If Grafana changes its markup, only this
 * folder changes; the specs stay the same.
 */
export class QualityDashboardPage {
  readonly ciOnMain: Panel;
  readonly openHighCriticalBugs: Panel;
  readonly failures: Panel;

  constructor(private readonly page: Page) {
    this.ciOnMain = this.panel("CI on main");
    this.openHighCriticalBugs = this.panel("Open High/Critical bugs");
    this.failures = this.panel("Failures");
  }

  /** Open the dashboard and wait until it has rendered. */
  async open(range = "now-7d"): Promise<this> {
    await this.page.goto(`/d/quality?orgId=1&from=${range}&to=now`);
    await this.ciOnMain.root.waitFor();
    return this;
  }

  panel(title: string): Panel {
    return new Panel(this.page, title);
  }
}
