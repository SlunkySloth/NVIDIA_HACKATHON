// Capture an actual investigation. Reference is the safe, credential-free default.
import {chromium, expect} from '@playwright/test';
import {spawn} from 'node:child_process';
import {mkdir, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../../..', import.meta.url));
const mode = process.env.REPLAYLAB_DEMO_MODE || 'reference';
if (!['reference', 'live'].includes(mode)) throw new Error('Demo mode must be reference or live');
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const output = path.join(root, 'docs/demo', `${mode}-${stamp}`);
await mkdir(output, {recursive: true});
const env = {...process.env, PYTHONPATH: path.join(root, 'backend'), REPLAYLAB_DATA_DIR: path.join(root, '.replaylab/demo'), REPLAYLAB_PUBLIC_DEMO: 'false', REPLAYLAB_SECURE_COOKIE: 'false'};
if (mode === 'reference') Object.assign(env, {NEBIUS_API_KEY: '', CONTREE_API_KEY: ''});
const server = spawn(path.join(root, '.venv/bin/python'), ['-m', 'replaylab.cli', 'serve', '--port', '8766'], {cwd: root, env, stdio: 'ignore'});
let serverError;
server.on('error', error => {serverError = error;});
let browser, context, video, started;
const scenes = [];
const seconds = () => (Date.now() - started) / 1000;
async function hold(id, narration, duration = 13) {
  const start = seconds();
  await new Promise(resolve => setTimeout(resolve, duration * 1000));
  scenes.push({id, start, end: seconds(), narration});
}
try {
  let healthy = false;
  for (let attempt = 0; attempt < 150; attempt++) {
    if (serverError || server.exitCode !== null) throw new Error('Demo API failed to start');
    try {
      const response = await fetch('http://127.0.0.1:8766/health');
      const health = await response.json();
      if (health.ready) {
        if (mode === 'live' && !health.live_configured) throw new Error('Live demo requires configured inference and Sandbox access');
        healthy = true;
        break;
      }
    } catch (error) {
      if (error.message.includes('requires configured')) throw error;
    }
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  if (!healthy) throw new Error('Demo API readiness deadline exceeded');
  browser = await chromium.launch(process.env.REPLAYLAB_BROWSER_PATH ? {executablePath: process.env.REPLAYLAB_BROWSER_PATH} : {});
  context = await browser.newContext({viewport: {width: 1440, height: 1000}, recordVideo: {dir: output, size: {width: 1440, height: 1000}}});
  const page = await context.newPage();
  video = page.video();
  started = Date.now();
  await page.goto('http://127.0.0.1:8766/');
  await expect(page.getByText('Workspace ready', {exact: true})).toBeVisible();
  await hold('overview', 'ReplayLab investigates webhook failures using explicit behavior contracts and independently observed business state. These three original synthetic examples cover duplicate credits, repeated fulfillment, and stale subscription updates.');
  await page.getByRole('button', {name: /Credits granted twice/}).click();
  await expect(page.getByRole('heading', {name: 'Review the behavior contract'})).toBeVisible();
  await hold('contract', 'Here, the same payment event arrives twice. HTTP success alone does not prove correctness. The reviewed contract requires one credit grant per event, while distinct legitimate purchases must still work.');
  await page.getByRole('checkbox', {name: 'I confirm this is the intended behavior.'}).check();
  const executionStart = seconds();
  await page.getByRole('button', {name: mode === 'live' ? 'Run live investigation' : 'Run reference investigation'}).click();
  await expect(page.getByRole('heading', {name: 'Verified for tested scenarios'})).toBeVisible({timeout: 500000});
  const executionEnd = seconds();
  scenes.push({id: 'execution', start: executionStart, end: executionEnd, compressed: true, narration: mode === 'live'
    ? 'This actual run uses an NVIDIA model through Nebius Token Factory to generate the regression and patch. Token Factory Sandboxes execute the candidate in clean environments. Waiting time is compressed.'
    : 'This local recording executes real services with a human-authored reference patch. It makes no model calls. Live NVIDIA generation and Nebius Sandbox execution still require account access. Waiting time is compressed.'});
  await expect(page.locator('.replay-column.original .business-value')).toHaveText('200credits');
  await expect(page.locator('.replay-column.candidate .business-value')).toHaveText('100credits');
  await hold('comparison', 'Both revisions receive the same events and start with the same database. The original grants two hundred credits; the candidate grants one hundred. Every value shown comes from an actual replay observation.');
  await page.getByRole('tab', {name: 'Code & regression'}).click();
  await expect(page.locator('.regression-status')).toContainText('1 collected · 0 passed · 1 failed');
  await expect(page.locator('.regression-status')).toContainText('1 collected · 1 passed · 0 failed');
  await page.locator('.regression-status').scrollIntoViewIfNeeded();
  await hold('regression', 'The regression must fail meaningfully on the original before a candidate is accepted. Here, it fails on the original and passes on the candidate. The displayed diff lets the reviewer inspect the change.');
  await page.getByRole('tab', {name: 'Replay comparison'}).click();
  await page.getByRole('combobox', {name: 'Scenario'}).selectOption('restart');
  await expect(page.locator('.replay-column.candidate .business-value')).toHaveText('100credits');
  await page.locator('.timeline-control').scrollIntoViewIfNeeded();
  await hold('restart', 'A passing incident regression is only the first challenge. ReplayLab restarts the service while retaining SQLite state, then retries delivery. This candidate keeps the credit grant correct across the restart.');
  await page.getByRole('tab', {name: 'Verification checks'}).click();
  await expect(page.getByRole('heading', {name: 'Independent scenario matrix'})).toBeVisible();
  await page.locator('.checks-panel .panel-foot').scrollIntoViewIfNeeded();
  await hold('matrix', 'Independent checks also test distinct events and separate entities. Final challenge scenarios are withheld from patch feedback. The verdict supports these tested scenarios; concurrency and external side effects remain outside the demonstrated scope.');
  await page.getByRole('tab', {name: 'Run details'}).click();
  await page.locator('.run-details').scrollIntoViewIfNeeded();
  const runId = await page.evaluate(() => localStorage.getItem('replaylab-current'));
  const response = await context.request.get(`http://127.0.0.1:8766/api/runs/${runId}`);
  const row = await response.json();
  const manifest = row.result.manifest;
  if (row.mode !== mode || row.state !== 'EXPORTED') throw new Error('Captured run does not match the requested mode and verdict');
  if (mode === 'live' && (!manifest.model_calls?.length || !manifest.sandbox_operation_ids?.length || !manifest.model_ids.every(id => /nvidia|nemotron/i.test(id)))) throw new Error('Live capture lacks actual NVIDIA and Sandbox evidence');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', {name: 'Export evidence'}).click();
  const download = await downloadPromise;
  await download.saveAs(path.join(output, 'evidence.zip'));
  await hold('evidence', 'The execution record and evidence export preserve the inputs, exact source, regression, observations, and hashes behind the verdict. ReplayLab makes the result inspectable and reproducible instead of asking the reviewer to trust a patch.');
  await writeFile(path.join(output, 'run.json'), JSON.stringify({id: row.id, mode: row.mode, state: row.state, result: row.result}, null, 2));
  await writeFile(path.join(output, 'capture.json'), JSON.stringify({schema_version: '1', captured_at: new Date().toISOString(), mode, run_id: runId, actual_run_elapsed_seconds: manifest.elapsed_seconds, scenes}, null, 2));
} finally {
  if (context) await context.close();
  if (video) await video.saveAs(path.join(output, 'raw.webm'));
  if (browser) await browser.close();
  server.kill('SIGTERM');
  await new Promise(resolve => {if (server.exitCode !== null) resolve(); else {server.once('exit', resolve); setTimeout(() => {server.kill('SIGKILL'); resolve();}, 3000).unref();}});
}
console.log(`Actual ${mode} capture saved: ${output}`);
