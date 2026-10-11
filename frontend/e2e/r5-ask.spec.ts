import { test, expect } from '@playwright/test';
import { createClearanceCase, goHome } from './helpers';

test.describe('@r5 ask', () => {
  test('case ask panel on Ask tab', async ({ page }) => {
    await goHome(page);
    await createClearanceCase(page, { title: `R5 ask ${Date.now()}` });

    await page.getByTestId('case-tab-ask').click();
    await expect(page.getByTestId('case-ask-panel')).toBeVisible();

    await page.getByTestId('nav-ask').click();
    await expect(page.getByTestId('ask-link-case')).toBeVisible();
    await expect(page.getByTestId('ask-shipment-select')).toBeVisible();
  });
});
