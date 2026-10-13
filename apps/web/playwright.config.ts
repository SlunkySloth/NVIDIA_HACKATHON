import {defineConfig} from '@playwright/test';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../..', import.meta.url));

export default defineConfig({
  testDir: './tests',
  timeout: 90000,
  expect: {timeout: 60000},
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:8765',
    viewport: {width: 1440, height: 1000},
    trace: 'retain-on-failure',
    launchOptions: process.env.REPLAYLAB_BROWSER_PATH
      ? {executablePath: process.env.REPLAYLAB_BROWSER_PATH}
      : {},
  },
  webServer: {
    command: `"${root}/.venv/bin/python" "${root}/scripts/browser_server.py" --port 8765`,
    url: 'http://127.0.0.1:8765/health',
    timeout: 90000,
    reuseExistingServer: false,
    env: {
      PYTHONPATH: `${root}/backend`,
      REPLAYLAB_DATA_DIR: `${root}/.replaylab/e2e`,
      REPLAYLAB_PUBLIC_DEMO: 'false',
      REPLAYLAB_SECURE_COOKIE: 'false',
      NEBIUS_API_KEY: '',
      CONTREE_API_KEY: '',
    },
  },
});
