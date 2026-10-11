import { test, expect } from '@playwright/test';
import { createClearanceCase, goHome } from './helpers';

test.describe('@r2 case workspace', () => {
  test('create case → classification tab → confirm if possible → close', async ({ page }) => {
    await goHome(page);
    await createClearanceCase(page, {
      title: `R2 case ${Date.now()}`,
      product: '100% cotton knit T-shirt',
    });

    await expect(page.getByTestId('scenario-overview')).toBeVisible();
    await expect(page.getByTestId('next-action-bar')).toBeVisible();
    await expect(page.getByTestId('case-file-tabs')).toBeVisible();

    await page.getByTestId('case-tab-classify').click();
    await expect(page.getByRole('heading', { name: /Classify product/i })).toBeVisible();

    const confirmBtn = page.getByRole('button', { name: 'Confirm HS' }).first();
    if (await confirmBtn.isVisible().catch(() => false)) {
      await confirmBtn.click();
      await expect(page.getByText(/Working HS/i).first()).toBeVisible({ timeout: 15_000 });
    }

    page.once('dialog', (d) => d.accept());
    await page.getByRole('button', { name: 'Close case' }).first().click();
    await expect(page.getByText('Closed').first()).toBeVisible({ timeout: 15_000 });
  });
});
