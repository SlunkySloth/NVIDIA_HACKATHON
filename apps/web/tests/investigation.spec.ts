import {expect, test} from '@playwright/test';
import {fileURLToPath} from 'node:url';

test('credits incident becomes reviewable evidence and survives reload', async ({page}) => {
  const browserErrors: string[] = [];
  page.on('pageerror', error => browserErrors.push(error.message));
  await page.goto('/');
  await expect(page.getByText('Workspace ready', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: /Credits granted twice/}).click();
  const runButton = page.getByRole('button', {name: 'Run reference investigation'});
  await expect(runButton).toBeDisabled();
  await page.getByRole('checkbox', {name: 'I confirm this is the intended behavior.'}).check();
  await runButton.click();
  await expect(page.getByRole('heading', {name: 'Verified for tested scenarios'})).toBeVisible();
  await expect(page.locator('.replay-column.original .business-value')).toHaveText('200credits');
  await expect(page.locator('.replay-column.candidate .business-value')).toHaveText('100credits');
  await page.screenshot({path: fileURLToPath(new URL('../../../docs/screenshots/replay-comparison.png', import.meta.url)), fullPage: true});
  await page.getByRole('combobox', {name: 'Scenario'}).selectOption('restart');
  await expect(page.locator('.replay-column.original .business-value')).toHaveText('200credits');
  await expect(page.locator('.replay-column.candidate .business-value')).toHaveText('100credits');
  await page.getByRole('tab', {name: 'Code & regression'}).click();
  await expect(page.locator('.diff')).toContainText('INSERT OR IGNORE INTO processed');
  await expect(page.locator('.regression-status')).toContainText('1 collected · 0 passed · 1 failed');
  await expect(page.locator('.regression-status')).toContainText('1 collected · 1 passed · 0 failed');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', {name: 'Export evidence'}).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('evidence.zip');
  expect(await download.failure()).toBeNull();
  await page.reload();
  await expect(page.getByRole('heading', {name: 'Verified for tested scenarios'})).toBeVisible();
  await page.getByRole('tab', {name: 'Run details'}).click();
  await expect(page.locator('.event-log')).toContainText('Original business-state violation reproduced');
  expect(browserErrors).toEqual([]);
});

test('flawed patch passes the incident regression but fails a restart', async ({page}) => {
  await page.goto('/');
  await page.getByRole('button', {name: /Credits granted twice/}).click();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', {name: 'Compare a pre-authored flawed patch'}).click();
  await expect(page.getByRole('heading', {name: 'Patch rejected', exact: true})).toBeVisible();
  await page.getByRole('combobox', {name: 'Scenario'}).selectOption('restart');
  await expect(page.locator('.replay-column.candidate .business-value')).toHaveText('200credits');
  await expect(page.locator('.replay-column.candidate .check-badge')).toContainText('Failed');
});

test('an active investigation can be cancelled and retried', async ({page}) => {
  await page.goto('/');
  await page.getByRole('button', {name: /An order fulfilled twice/}).click();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', {name: 'Run reference investigation'}).click();
  await page.getByRole('button', {name: 'Cancel', exact: true}).click();
  await expect(page.getByRole('button', {name: 'Run again'})).toBeVisible();
  await page.getByRole('button', {name: 'Run again'}).click();
  await expect(page.getByRole('heading', {name: 'Verified for tested scenarios'})).toBeVisible();
});

test('a recorded investigation is labeled, reloadable, and read-only', async ({page}) => {
  const writes: string[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/runs')) writes.push(request.url());
  });
  await page.goto('/');
  await page.getByRole('button', {name: /RECORDED.*HUMAN-AUTHORED REFERENCE/}).first().click();
  await expect(page.locator('.recorded-notice')).toContainText('No new generation or execution occurs');
  await expect(page.getByRole('heading', {name: 'Verified for tested scenarios'})).toBeVisible();
  await page.getByRole('tab', {name: 'Verification checks'}).click();
  await expect(page.getByRole('heading', {name: 'Independent scenario matrix'})).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', {name: 'Export evidence'}).click();
  expect((await downloadPromise).suggestedFilename()).toBe('evidence.zip');
  await page.reload();
  await expect(page.locator('.recorded-notice')).toBeVisible();
  expect(writes).toEqual([]);
  await page.getByRole('button', {name: 'Start a new investigation'}).click();
  await expect(page.getByRole('heading', {name: 'Review the behavior contract'})).toBeVisible();
  await expect(page.getByRole('checkbox')).not.toBeChecked();
});
