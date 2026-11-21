import { test as base } from "@playwright/test";
import { QualityDashboardPage } from "./pages/QualityDashboardPage";

/**
 * Custom fixtures: the TypeScript counterpart of the `dashboard` fixture in tests/ui/conftest.py.
 * Each test receives a dashboard that is already open, so no spec repeats the setup.
 */
type Fixtures = { dashboard: QualityDashboardPage };

export const test = base.extend<Fixtures>({
  dashboard: async ({ page }, use) => {
    await use(await new QualityDashboardPage(page).open());
  },
});

export { expect } from "@playwright/test";
