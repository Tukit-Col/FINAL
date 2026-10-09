// E2E de UI del acudiente (fase 4, paso 2 de la skill de QA) contra el stack vivo.
//
//   make backend                                   # el gateway en :8010 y los servicios
//   npm ci && npm run build:web                    # en la raiz del monorepo
//   cd apps/web/e2e && npm ci && npx playwright install chromium && npx playwright test
//
// Si la web no esta arriba en :3000, `webServer` la levanta con `next start` (hace falta el build).
// `QA_JUNIT` elige donde queda el JUnit, con `ensayo_id` y `correlacion_id` como propiedades de cada
// caso (acuerdos.md §2.4). `QA_RUNXFAIL=1` corre los `test.fail` como pruebas normales, igual que
// `pytest --runxfail`, para confirmar que fallan en su asercion.

import { defineConfig, devices } from "@playwright/test";

const WEB = process.env.TUKIT_WEB_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.mjs",
  workers: 1,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  reporter: [
    ["list"],
    [
      "junit",
      { outputFile: process.env.QA_JUNIT ?? "test-results/junit.xml", embedAnnotationsAsProperties: true },
    ],
  ],
  use: { baseURL: WEB, trace: "off", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run start --workspace @tukit/web",
    cwd: "../../..",
    url: `${WEB}/ingresar`,
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      TUKIT_API_URL: process.env.TUKIT_API_URL ?? "http://127.0.0.1:8010",
      NEXT_TELEMETRY_DISABLED: "1",
    },
  },
});
