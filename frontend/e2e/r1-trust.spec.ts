import { test, expect } from '@playwright/test';
import { goHome } from './helpers';

test.describe('@r1 trust', () => {
  test('home loads without demo status banner', async ({ page }) => {
    await goHome(page);
    await expect(page.locator('.environment-banner')).toHaveCount(0);
    await expect(page.getByTestId('nav-dashboard')).toBeVisible();
    await expect(page.getByRole('button', { name: 'New clearance case' })).toBeVisible();
  });

  test('coverage miss path shows next-step panel on tariffs', async ({ page }) => {
    await goHome(page);
    await page.getByTestId('nav-tariffs').click();
    const hsInput = page.locator('input').first();
    await hsInput.fill('9999.99');
    const searchBtn = page.getByRole('button', { name: /search|look up|find/i }).first();
    if (await searchBtn.isVisible().catch(() => false)) {
      await searchBtn.click();
    } else {
      await hsInput.press('Enter');
    }
    await expect(
      page
        .getByTestId('coverage-miss')
        .or(page.locator('.coverage-miss'))
        .or(page.getByText(/not covered|no approved|coverage/i)),
    ).toBeVisible({ timeout: 15_000 });
  });
});
