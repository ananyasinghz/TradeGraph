import { test, expect } from '@playwright/test';
import { goHome } from './helpers';

test.describe('@r6 admin', () => {
  test('admin nav visible with auth off (anonymous admin)', async ({ page }) => {
    await goHome(page);
    // Backend auth off → whoami.role is admin
    await expect(page.getByTestId('nav-admin')).toBeVisible();
    await page.getByTestId('nav-admin').click();
    await expect(page.getByTestId('ingest-pending-filter')).toBeVisible();
    await expect(page.getByTestId('admin-users-section')).toBeVisible();
    await expect(page.getByTestId('admin-demo-session')).toBeVisible();
    await expect(page.getByTestId('admin-role-summary')).toBeVisible();
    await expect(page.getByTestId('role-chip-viewer')).toHaveText('viewer');
    await expect(page.getByTestId('role-chip-operator')).toHaveText('operator');
    await expect(page.getByTestId('role-chip-reviewer')).toHaveText('reviewer');
    await expect(page.getByTestId('role-chip-admin')).toHaveText('admin');
    await expect(page.getByTestId('sources-feed-health')).toBeVisible();
    await expect(page.getByTestId('sources-connections-table')).toBeVisible();
    await expect(page.getByTestId('sources-fetch-honesty')).toBeVisible();
  });

  test('load notice shows eligibility; make rates live enabled when ok > 0', async ({
    page,
  }) => {
    await goHome(page);
    await page.getByTestId('nav-admin').click();
    await page.getByRole('button', { name: 'Load CBIC Q3 notice' }).click();
    await expect(page.getByTestId('ingest-review-panel')).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId('publish-eligibility-banner')).toBeVisible();
    await expect(page.getByTestId('review-eligibility-table')).toBeVisible();
    await expect(page.getByTestId('eligibility-eligible').first()).toBeVisible();
    await expect(page.getByTestId('eligibility-quarantined').first()).toBeVisible();
    const makeLive = page.getByTestId('make-rates-live');
    await expect(makeLive).toBeVisible();
    await expect(makeLive).toBeEnabled();
  });
});
