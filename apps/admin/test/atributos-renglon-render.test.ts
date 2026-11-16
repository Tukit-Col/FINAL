// Prueba de render de «Atributos que se exigen» (`AtributosRenglon.tsx`) sin
// navegador: `react-dom/server` lo pinta a HTML y se buscan los valores y las
// marcas que distinguen cada clase de atributo (leído, curado, no exigido).
//
// El admin no tiene runner de componentes y no se le agrega uno: `node --test`
// no entiende `.tsx` ni el alias `@/`, así que esta prueba transpila el
// componente con el `typescript` que ya está en las devDependencies (a
// CommonJS, en memoria) y le pasa un `require` que resuelve `@/` a `src/`, el
// CSS module a un objeto que devuelve el nombre de la clase, y el resto
// (`react`) a `node_modules`. Nada se escribe a disco.
//
// Correr:  node --test test/atributos-renglon-render.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const requerir = createRequire(import.meta.url);
const ts = requerir("typescript");
const React = requerir("react");
const { renderToStaticMarkup } = requerir("react-dom/server");
const SRC = fileURLToPath(new URL("../src/", import.meta.url));

type Modulo = Record<string, unknown>;
const cargados = new Map<string, Modulo>();

/** Carga un fuente de `src/` transpilado a CommonJS, con sus imports resueltos. */
function cargar(ruta: string): Modulo {
  const archivo = [ruta, `${ruta}.ts`, `${ruta}.tsx`].map((r) => path.join(SRC, r)).find(existsSync);
  if (!archivo) throw new Error(`no encuentro ${ruta} en src/`);
  const previo = cargados.get(archivo);
  if (previo) return previo;
  const { outputText } = ts.transpileModule(readFileSync(archivo, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true,
    },
    fileName: archivo,
  });
  const modulo = { exports: {} as Modulo };
  cargados.set(archivo, modulo.exports);
  const requerirDesdeSrc = (id: string): unknown => {
    if (id.endsWith(".module.css")) {
      // `styles.atributo` → "atributo". Sin `__esModule`, para que el
      // `import styles from` transpilado lo tome como el default.
      return new Proxy({}, { get: (_, k) => (k === "__esModule" ? undefined : String(k)) });
    }
    if (id.startsWith("@/")) return cargar(id.slice(2));
    return requerir(id);
  };
  new Function("require", "module", "exports", outputText)(requerirDesdeSrc, modulo, modulo.exports);
  return modulo.exports;
}

const { default: AtributosRenglon } = cargar("components/AtributosRenglon");
const filasDeExigencia = cargar("lib/atributos-renglon").filasDeExigencia as (item: Modulo) => unknown;

function pintar(item: Modulo, extra: Modulo = {}): string {
  return renderToStaticMarkup(
    React.createElement(AtributosRenglon, {
      itemId: "i1",
      filas: filasDeExigencia(item),
      onCambio: () => {},
      discriminantes: item.atributos_discriminantes,
      porRevisar: [],
      sugerencias: {},
      conceptoCambiado: false,
      disabled: false,
      ...extra,
    }),
  );
}

// La bitácora de la guía (§5.6), con un atributo de cada clase: `hojas` solo
// leído, `tipo` curado sobre lo leído y `tamano` curado con `*`.
const bitacora = {
  atributos_discriminantes: ["tipo", "tamano", "hojas", "color"],
  atributos_leidos: { tipo: "cartulina", tamano: "octavo", hojas: 15 },
  atributos_deducidos: [],
  atributos: { tipo: "dibujo", tamano: "*" },
};

test("pinta lo leído, lo curado y lo que no se exige, cada uno con su texto", () => {
  const html = pintar(bitacora);

  assert.match(html, /Atributos que se exigen/);
  // Leído sin curar: se exige lo del texto, sin la marca de curado.
  assert.match(html, /del texto: 15/);
  assert.match(html, /Se exige: 15</);
  // Curado sobre lo leído: manda lo curado, y se puede volver a lo leído.
  assert.match(html, /del texto: cartulina/);
  assert.match(html, /value="dibujo"/);
  assert.match(html, /Se exige: dibujo · curado/);
  // Con `*`: «No exigir» marcado y el atributo no se exige.
  assert.match(html, /del texto: octavo/);
  assert.match(html, /No se exige · curado/);
  assert.equal(html.match(/checked=""/g)?.length, 1);
  assert.equal(html.match(/Volver a lo leído/g)?.length, 2);
  // El discriminante que ni se lee ni se cura se ofrece para agregar.
  assert.match(html, /<option value="color"[^>]*>color<\/option>/);
  assert.match(html, /\+ Exigir atributo/);
});

test("el «más de uno» deducido lleva su nota", () => {
  const html = pintar({
    atributos_discriminantes: ["unidades"],
    atributos_leidos: { unidades: 2 },
    atributos_deducidos: ["unidades"],
    atributos: {},
  });
  assert.match(html, /deducido: más de uno/);
  // La nota explica que, si no hay juego, vale la pieza suelta.
  assert.match(html, /pieza suelta/);
  assert.match(html, /Se exige: más de uno/);
  assert.doesNotMatch(html, /del texto: 2/);
});

test("con el concepto cambiado no ofrece curar: pide guardar primero", () => {
  const html = pintar(bitacora, { conceptoCambiado: true });
  // Avisa del concepto cambiado y no pinta ningun control de curado.
  assert.match(html, /concepto/);
  assert.doesNotMatch(html, /No exigir/);
  assert.doesNotMatch(html, /<input/);
});
