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

const bitacora = {
  atributos_discriminantes: ["tipo", "tamano", "hojas", "color"],
  atributos_leidos: { tipo: "cartulina", tamano: "octavo", hojas: 15 },
  atributos_deducidos: [],
  atributos: { tipo: "dibujo", tamano: "*" },
};

test("pinta lo leído, lo curado y lo que no se exige, cada uno con su texto", () => {
  const html = pintar(bitacora);

  assert.match(html, /Atributos que se exigen/);
  assert.match(html, /del texto: 15/);
  assert.match(html, /Se exige: 15</);
  assert.match(html, /del texto: cartulina/);
  assert.match(html, /value="dibujo"/);
  assert.match(html, /Se exige: dibujo · curado/);
  assert.match(html, /del texto: octavo/);
  assert.match(html, /No se exige · curado/);
  assert.equal(html.match(/checked=""/g)?.length, 1);
  assert.equal(html.match(/Volver a lo leído/g)?.length, 2);
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
  assert.match(html, /pieza suelta/);
  assert.match(html, /Se exige: más de uno/);
  assert.doesNotMatch(html, /del texto: 2/);
});

test("con el concepto cambiado no ofrece curar: pide guardar primero", () => {
  const html = pintar(bitacora, { conceptoCambiado: true });
  assert.match(html, /concepto/);
  assert.doesNotMatch(html, /No exigir/);
  assert.doesNotMatch(html, /<input/);
});
