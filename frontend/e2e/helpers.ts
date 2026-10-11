import { expect, type Page } from '@playwright/test';

export async function dismissWelcomeIfPresent(page: Page) {
  const skip = page.getByRole('button', { name: 'Skip for now' });
  if (await skip.isVisible().catch(() => false)) {
    await skip.click();
  }
}

export async function goHome(page: Page) {
  await page.goto('/');
  await dismissWelcomeIfPresent(page);
  await expect(page.getByTestId('nav-dashboard')).toBeVisible();
}

/** Open create form when hidden (list-first Clearance cases). */
export async function openCaseCreateForm(page: Page) {
  const form = page.getByTestId('case-create-form');
  if (await form.isVisible().catch(() => false)) return;
  const newBtn = page
    .getByTestId('case-new-btn')
    .or(page.getByRole('button', { name: 'New clearance case' }));
  await newBtn.first().click();
  await expect(form).toBeVisible();
}

export async function expectCaseFocus(page: Page) {
  await expect(page).toHaveURL(/#\/case\//);
  await expect(page.getByTestId('case-focus')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId('scenario-overview')).toBeVisible({ timeout: 20_000 });
}

export async function createClearanceCase(
  page: Page,
  opts: { title?: string; product?: string } = {},
) {
  const title = opts.title ?? `E2E case ${Date.now()}`;
  const product = opts.product ?? '100% cotton knit T-shirt';

  await page.getByTestId('nav-dashboard').click();
  await page.getByRole('button', { name: 'New clearance case' }).click();
  await openCaseCreateForm(page);

  await page.getByTestId('case-title-input').fill(title);
  await page.getByTestId('case-product-input').fill(product);

  await page.getByRole('button', { name: 'Create clearance case' }).click();

  try {
    await expectCaseFocus(page);
  } catch {
    // Create may succeed while navigation races — open from list.
    await expect(page.getByTestId('case-list')).toBeVisible({ timeout: 15_000 });
    const row = page.locator(`button[data-case-title="${title}"]`).first();
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.click();
    await expectCaseFocus(page);
  }
  return title;
}
