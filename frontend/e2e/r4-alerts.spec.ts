import { test, expect } from '@playwright/test';
import { goHome } from './helpers';

test.describe('@r4 alerts', () => {
  test('dashboard queue filter chips are visible', async ({ page }) => {
    await goHome(page);
    await expect(page.getByTestId('dashboard-queue-filter')).toBeVisible();
    await expect(page.getByTestId('queue-all')).toBeVisible();
    await expect(page.getByTestId('queue-blocked')).toBeVisible();
    await expect(page.getByTestId('queue-alerts')).toBeVisible();

    await page.getByTestId('queue-blocked').click();
    await expect(page.getByTestId('queue-blocked')).toHaveClass(/chip-active/);
  });
});
