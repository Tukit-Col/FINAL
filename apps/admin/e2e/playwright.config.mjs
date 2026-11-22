// E2E de UI de la revision en la consola (fase 4, paso 2 de la skill de QA) contra el stack vivo.
//
//   make backend                                   # el gateway en :8010 y los servicios
//   npm ci && npm run build:web && npm run build:admin    # en la raiz del monorepo
//   cd apps/admin/e2e && npm ci && npx playwright install chromium && npx playwright test
//
// El administrador entra por el login de la web (:3000), que pone la cookie y lo manda a la consola
// (:3001); por eso se levantan las dos apps con `next start` si no estan arriba (hace falta el build).
// `QA_JUNIT` elige donde queda el JUnit, con `ensayo_id` y `correlacion_id` como propiedades de cada
// caso (acuerdos.md §2.4). `QA_RUNXFAIL=1` corre los `test.fail` como pruebas normales, igual que
// `pytest --runxfail`, para confirmar que fallan en su asercion.

import { defineConfig, devices } from "@playwright/test";

const WEB = process.env.TUKIT_WEB_URL ?? "http://localhost:3000";
const ADMIN = process.env.TUKIT_ADMIN_URL ?? "http://localhost:3001";
const ENTORNO = {
  TUKIT_API_URL: process.env.TUKIT_API_URL ?? "http://127.0.0.1:8010",
  TUKIT_WEB_URL: WEB,
  TUKIT_ADMIN_URL: ADMIN,
  NEXT_TELEMETRY_DISABLED: "1",
  // La web que se levanta aqui tampoco carga Google Places (ADR 0044, decision N-129).
  GOOGLE_MAPS_API_KEY: "",
  // Ni la web ni la consola consultan OpenStreetMap: sin contacto no hay busqueda ni mapa de entregas
  // (ADR 0049, decision N-147).
  TUKIT_NOMINATIM_CONTACTO: "",
};

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
  use: { baseURL: ADMIN, trace: "off", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "npm run start --workspace @tukit/web",
      cwd: "../../..",
      url: `${WEB}/ingresar`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: ENTORNO,
    },
    {
      command: "npm run start --workspace @tukit/admin",
      cwd: "../../..",
      url: `${ADMIN}/cola`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: ENTORNO,
    },
  ],
});
