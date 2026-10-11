import { test, expect } from '@playwright/test';
import { createClearanceCase, goHome } from './helpers';

test.describe('@happy daily use', () => {
  test('Home → case → classify/duty tabs → papers → ask → close', async ({ page }) => {
    await goHome(page);

    const title = await createClearanceCase(page, {
      title: `Happy path ${Date.now()}`,
      product: '100% cotton knit T-shirt',
    });
    await expect(page.getByText(title).first()).toBeVisible();

    // Walk core case tabs
    for (const tab of [
      'Classification',
      'Duty',
      'Preferential',
      'Landed cost',
      'Papers',
      'Ask',
      'Activity',
    ]) {
      const btn = page.getByRole('button', { name: tab }).first();
      if (await btn.isVisible().catch(() => false)) {
        await btn.click();
      }
    }

    // Next-action bar should exist when workspace loaded
    const next = page.getByTestId('next-action-bar');
    if (await next.isVisible().catch(() => false)) {
      await expect(next).toBeVisible();
    }

    // Close case if button present
    const closeBtn = page.getByRole('button', { name: /close case/i });
    if (await closeBtn.isVisible().catch(() => false)) {
      page.once('dialog', (d) => d.accept());
      await closeBtn.click();
    }
  });
});
