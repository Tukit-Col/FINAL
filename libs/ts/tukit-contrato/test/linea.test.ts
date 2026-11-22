import { test } from "node:test";
import assert from "node:assert/strict";
import {
  clasificar,
  dondeComprar,
  esLibro,
  esUniforme,
  estadoDePrecio,
  etiquetaEmpaque,
  hayQueCobrar,
  instruccionCorta,
  lineasQueSuman,
  razonDeNoCobrar,
} from "../src/linea.ts";
import type { LineaKit, ProductoKit } from "../src/contrato.ts";

function linea(extra: Partial<LineaKit>): LineaKit {
  return {
    item_id: "i-1",
    orden: 64,
    descripcion: "Cuaderno",
    tipo: "util",
    estado_resolucion: "RESUELTO_AUTO",
    informativa: false,
    subtotal_linea: 9000,
    ...extra,
  } as LineaKit;
}

function producto(extra: Partial<ProductoKit>): ProductoKit {
  return {
    sku: "TK-1",
    nombre: "Cuaderno",
    marca: "Norma",
    nivel: "confiable",
    personaje: null,
    imagen_url: null,
    confianza: 1,
    ofertas: [],
    ...extra,
  };
}

function tituloSinCobro(l: LineaKit): string {
  const e = estadoDePrecio(l);
  assert.equal(e.tipo, "sin_cobro", `se esperaba una linea sin cobro y fue ${e.tipo}`);
  return e.tipo === "sin_cobro" ? e.titulo : "";
}

const LIBRERIA =
  "Se compra en librería: Tukit no tiene esta edición verificada en una tienda en línea. Verificado el 2026-11-01 en Buscalibre Colombia y en la lista del colegio.";
const PAPELERIA =
  "Se compra en papelería: Tukit no encontró este artículo con esa medida y ese formato en una tienda en línea (búsqueda del 2026-11-01 en Éxito y Panamericana). Cómpralo como lo pide el colegio.";
const COLEGIO =
  "No se compra en Tukit ni en una tienda en línea: la lista del colegio describe el modelo, pero no nombra una tienda para esta prenda. Pregunta en el colegio (601 427 2365). Verificado en la lista de textos y útiles 2026 y en la Circular 03 de 2026 del colegio el 2026-11-01.";

test("una linea que ya va en otra dice donde", () => {
  const juntada = linea({
    unidades_a_comprar: 0,
    mensaje: "Ya va en la linea 59: sirve para todas las materias.",
  });
  assert.equal(razonDeNoCobrar(juntada), "Ya va en la linea 59: sirve para todas las materias.");
});

test("una linea que se compra no tiene razon de no cobrar", () => {
  assert.equal(razonDeNoCobrar(linea({ unidades_a_comprar: 1 })), null);
});

test("un libro con titulo que no vendemos se consigue por tu cuenta, no es un hueco", () => {
  const libro = linea({
    descripcion: "Los secretos de Hafiz Mustafá - Francisco Leal Quevedo. Editorial Norma.",
    tipo: "libro_libre",
    estado_resolucion: "HUECO_CATALOGO",
  });
  assert.equal(clasificar(libro), "por_su_cuenta");
  assert.equal(clasificar({ ...libro, estado_resolucion: "SIN_MATCH" }), "sin_match");
  assert.equal(
    clasificar({ ...libro, estado_resolucion: "RESUELTO_AUTO", producto_elegido: { sku: "X" } } as LineaKit),
    "comprable",
  );
});

test("una linea con subtotal real muestra su precio", () => {
  assert.deepEqual(estadoDePrecio(linea({})), { tipo: "precio", valor: 9000 });
});

test("una linea comprable en cero nunca muestra 0: dice que no tiene precio y donde comprarla", () => {
  const sinPrecio = linea({
    subtotal_linea: 0,
    producto_elegido: producto({ ofertas: [{ tienda: "Panamericana", precio: 0, vigente_hasta: null }] }),
  });
  const titulo = tituloSinCobro(sinPrecio);
  assert.match(titulo, /Sin precio/);
  assert.match(titulo, /Panamericana/);
  const sinNada = tituloSinCobro(linea({ subtotal_linea: null }));
  assert.match(sinNada, /Sin precio/);
  assert.doesNotMatch(sinNada, /se compra en/i);
});

test("el catalogo manda: si dice donde se compra, esa tienda gana", () => {
  const l = linea({
    subtotal_linea: null,
    se_compra_en: "Librería Nacional",
    producto_elegido: producto({ ofertas: [{ tienda: "Otra", precio: 1, vigente_hasta: null }] }),
  });
  assert.equal(dondeComprar(l), "Librería Nacional");
});

test("lo que entrega el colegio, las licencias y los uniformes dicen como conseguirlos", () => {
  assert.match(tituloSinCobro(linea({ informativa: true, subtotal_linea: null })), /colegio/i);

  const licencia = tituloSinCobro(
    linea({ tipo: "licencia_digital", informativa: true, subtotal_linea: null, url_externa: "https://www.quovix.com/comprar" }),
  );
  assert.match(licencia, /^Licencia digital/);
  assert.match(licencia, /quovix\.com$/);

  const uniforme = tituloSinCobro(linea({ tipo: "uniforme", subtotal_linea: null, se_compra_en: "Uniformes Lupita" }));
  assert.match(uniforme, /^Uniforme/);
  assert.match(uniforme, /Uniformes Lupita/);
});

test("un libro de texto dice la editorial y un uniforme se reconoce como tal", () => {
  const libro = linea({
    tipo: "texto",
    informativa: true,
    subtotal_linea: null,
    edicion: { isbn13: "1", titulo: "Matemáticas 4", editorial: "Santillana", anio_edicion: 2026 },
  });
  assert.equal(esLibro(libro), true);
  assert.equal(esUniforme(libro), false);
  const titulo = tituloSinCobro(libro);
  assert.match(titulo, /^Libro/);
  assert.match(titulo, /Santillana/);
  assert.equal(esUniforme(linea({ tipo: "uniforme" })), true);
});

test("una linea descartada dice cuanto se ahorra y no cuenta en el total", () => {
  const descartada = linea({ descartado: true, subtotal_linea: null, subtotal_descartado: 9000 });
  assert.deepEqual(estadoDePrecio(descartada), { tipo: "descartado", ahorro: 9000 });
  assert.deepEqual(lineasQueSuman([linea({}), descartada]).length, 1);
});

test("un total en cero no se cobra ni se muestra como $ 0", () => {
  assert.equal(hayQueCobrar(0), false);
  assert.equal(hayQueCobrar(null), false);
  assert.equal(hayQueCobrar(18900), true);
});

test("el empaque se dice como empaque", () => {
  assert.equal(etiquetaEmpaque(12, 1), "Empaque de 12");
  assert.equal(etiquetaEmpaque(1, 1), "Por unidad");
  assert.equal(etiquetaEmpaque(12, 2), "Empaque de 12 · compras 2");
});

test("la instruccion del colegio se dice corta: la frase, sin la fuente ni la fecha", () => {
  assert.equal(instruccionCorta(linea({ instruccion_colegio: LIBRERIA })), "Se compra en librería");
  assert.equal(instruccionCorta(linea({ instruccion_colegio: PAPELERIA })), "Se compra en papelería");
  assert.equal(instruccionCorta(linea({ instruccion_colegio: COLEGIO })), "Pregunta en el colegio (601 427 2365)");
  assert.equal(instruccionCorta(linea({ instruccion_colegio: null })), null);
  assert.equal(instruccionCorta(linea({ instruccion_colegio: "x".repeat(80) })), null);
});

test("un libro del plan lector sin edicion va con los libros y dice que se compra en libreria", () => {
  const l = linea({ tipo: "otro", concepto: "C134", informativa: true, subtotal_linea: null, instruccion_colegio: LIBRERIA });
  assert.equal(esLibro(l), true);
  const titulo = tituloSinCobro(l);
  assert.match(titulo, /^Libro/);
  assert.match(titulo, /librería/);
  assert.equal(razonDeNoCobrar(l), LIBRERIA);
  const sinConcepto = linea({ tipo: "otro", informativa: true, subtotal_linea: null, instruccion_colegio: LIBRERIA });
  assert.equal(esLibro(sinConcepto), true);
  assert.equal(esLibro(linea({ tipo: "no_comprar", concepto: "C134" })), false);
  assert.equal(esLibro(linea({ tipo: "otro", instruccion_colegio: PAPELERIA })), false);
});

test("un uniforme sin tienda dice que se pregunta en el colegio, con el telefono", () => {
  const l = linea({ tipo: "uniforme", informativa: true, subtotal_linea: null, instruccion_colegio: COLEGIO });
  const titulo = tituloSinCobro(l);
  assert.match(titulo, /^Uniforme/);
  assert.match(titulo, /pregunta en el colegio/i);
  assert.match(titulo, /601 427 2365/);
  assert.equal(razonDeNoCobrar(l), COLEGIO);
});

test("lo que se compra en papeleria lo dice en la linea, y una tienda del catalogo sigue ganando", () => {
  const l = linea({ tipo: "otro", informativa: true, subtotal_linea: null, instruccion_colegio: PAPELERIA });
  assert.match(tituloSinCobro(l), /papelería/);
  const conTienda = linea({ tipo: "uniforme", subtotal_linea: null, se_compra_en: "Uniformes Lupita", instruccion_colegio: COLEGIO });
  const titulo = tituloSinCobro(conTienda);
  assert.match(titulo, /Uniformes Lupita/);
  assert.doesNotMatch(titulo, /pregunta en el colegio/i);
});
