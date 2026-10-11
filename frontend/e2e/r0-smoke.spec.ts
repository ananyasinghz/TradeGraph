import { test, expect } from '@playwright/test';
import { createClearanceCase, goHome } from './helpers';

test.describe('@r0 smoke', () => {
  test('API health is reachable via proxy', async ({ request }) => {
    const res = await request.get('http://127.0.0.1:8000/api/v1/health');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status || body.ok || body).toBeTruthy();
  });

  test('Home loads and creates a clearance case workspace', async ({ page }) => {
    await goHome(page);
    await expect(page.getByRole('button', { name: 'New clearance case' })).toBeVisible();

    const title = await createClearanceCase(page);
    await expect(page.getByText(title).first()).toBeVisible();
    await expect(page.getByTestId('scenario-overview')).toBeVisible();
  });
});
