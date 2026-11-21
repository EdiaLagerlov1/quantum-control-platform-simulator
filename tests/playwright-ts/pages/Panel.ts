import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Component object: one Grafana panel.
 *
 * A page object does not have to model a whole page. A repeated widget gets its own class,
 * and the page object hands out instances of it.
 */
export class Panel {
  readonly root: Locator;
  readonly canvas: Locator;

  constructor(page: Page, readonly title: string) {
    // Grafana marks every panel with a test id built from its title.
    this.root = page.getByTestId(`data-testid Panel header ${title}`);
    this.canvas = this.root.locator("canvas");
  }

  /** Domain-level assertion: the panel is on screen and has data. */
  async expectToShowData(): Promise<void> {
    await expect(this.root, `panel "${this.title}" is missing`).toBeVisible();
    await expect(this.root, `panel "${this.title}" has no data`).not.toContainText("No data");
  }

  /** A chart draws on a <canvas>. No canvas means an empty box, even with good data. */
  async expectChartDrawn(): Promise<void> {
    await expect(this.canvas, `chart "${this.title}" was not drawn`).toHaveCount(1);
  }
}
