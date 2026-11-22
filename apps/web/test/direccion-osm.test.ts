import { test } from "node:test";
import assert from "node:assert/strict";
import { direccionDesdeNominatim } from "../../../libs/ts/tukit-contrato/src/localidades.ts";
import {
  agenteUsuario,
  BuscadorOsm,
  ErrorBusqueda,
  formatearDireccion,
  formatearPlaca,
  leerCandidatos,
  parsearNomenclatura,
  normalizarConsulta,
} from "../src/lib/direccion-osm.ts";

const CHAPINERO = {
  place_id: 1,
  osm_type: "way",
  osm_id: 4455,
  lat: "4.6518184",
  lon: "-74.0510026",
  category: "highway",
  name: "Calle 72",
  address: {
    road: "Calle 72",
    house_number: "10-34",
    neighbourhood: "UPZs de Bogotá",
    suburb: "Localidad Chapinero",
    city: "Bogotá ciudad",
    state: "Bogotá, Distrito Capital",
  },
};
const MADRID = { ...CHAPINERO, osm_id: 9, lat: "40.4168", lon: "-3.7038" };

function armar(respuestas: (url: URL) => unknown | Error) {
  const llamadas: { url: URL; ua: string | null; t: number }[] = [];
  let reloj = 1_000_000;
  const buscador = new BuscadorOsm({
    contacto: "ops@tukit.co",
    ahora: () => reloj,
    esperar: async (ms) => {
      reloj += ms;
    },
    fetchFn: (async (url: URL, init: RequestInit) => {
      llamadas.push({ url, ua: (init.headers as Record<string, string>)["User-Agent"] ?? null, t: reloj });
      const r = respuestas(url);
      if (r instanceof Error) throw r;
      return { ok: true, status: 200, json: async () => r } as Response;
    }) as unknown as typeof fetch,
  });
  return { buscador, llamadas, avanzar: (ms: number) => (reloj += ms) };
}

test("las abreviaturas colombianas se expanden y el # no estorba", () => {
  assert.equal(normalizarConsulta("Cra 7 # 72-41"), "Carrera 7 72-41");
  assert.equal(normalizarConsulta("  Cl. 72  No. 10-34  "), "Calle 72 10-34");
  assert.equal(normalizarConsulta("Av. Boyacá"), "Avenida Boyacá");
  assert.equal(normalizarConsulta("Kr 15 # 93-60"), "Carrera 15 93-60");
});

test("el User-Agent identifica la app y trae el contacto", () => {
  assert.match(agenteUsuario("ops@tukit.co"), /^TukitWeb\/\d.*ops@tukit\.co/);
});

test("lee la dirección, el punto y la localidad, y descarta lo de fuera de Colombia", () => {
  const [unico, ...resto] = leerCandidatos([CHAPINERO, MADRID, "basura", null, { lat: "x", lon: "y" }]);
  assert.equal(resto.length, 0);
  assert.equal(unico?.direccion, "Calle 72 #10-34");
  assert.equal(unico?.latitud, 4.6518184);
  assert.equal(unico?.longitud, -74.0510026);
  assert.equal(unico?.secundario, "Localidad Chapinero, Bogotá");
  assert.equal(unico?.componentes["suburb"], "Localidad Chapinero");
});

test("dos resultados del mismo punto no se repiten", () => {
  assert.equal(leerCandidatos([CHAPINERO, { ...CHAPINERO, osm_id: 5 }]).length, 1);
});

test("un sitio se muestra por su nombre pero guarda su dirección", () => {
  const colegio = {
    osm_type: "node",
    osm_id: 7,
    lat: "4.7008",
    lon: "-74.0714",
    category: "amenity",
    name: "Colegio Agustiniano Norte",
    address: { amenity: "Colegio Agustiniano Norte", road: "Avenida Calle 116", suburb: "Localidad Suba", city: "Bogotá ciudad", state: "Bogotá, Distrito Capital" },
  };
  const [c] = leerCandidatos([colegio]);
  assert.equal(c?.principal, "Colegio Agustiniano Norte");
  assert.equal(c?.direccion, "Avenida Calle 116");
});

test("de Nominatim a ciudad, departamento y localidad canónicos", () => {
  assert.deepEqual(direccionDesdeNominatim(CHAPINERO.address), {
    ciudad: "Bogotá",
    departamento: "Bogotá, D.C.",
    localidad: "Chapinero",
  });
  assert.deepEqual(direccionDesdeNominatim({ town: "Chía", state: "Cundinamarca", suburb: "Fonqueta" }), {
    ciudad: "Chía",
    departamento: "Cundinamarca",
    localidad: "",
  });
  assert.equal(direccionDesdeNominatim({ city: "Bogotá ciudad", state: "Bogotá, Distrito Capital" }).localidad, "");
  assert.equal(direccionDesdeNominatim(null).ciudad, "");
});

test("la consulta sesga a Bogotá, pide Colombia y manda el contacto", async () => {
  const { buscador, llamadas } = armar(() => [CHAPINERO]);
  const r = await buscador.buscar("Cra 7 # 72-41");
  assert.equal(r.length, 1);
  const { url, ua } = llamadas[llamadas.length - 1]!;
  assert.equal(url.searchParams.get("countrycodes"), "co");
  assert.equal(url.searchParams.get("viewbox"), "-74.35,4.95,-73.90,4.40");
  assert.equal(url.searchParams.get("bounded"), "1");
  assert.equal(url.searchParams.get("q"), "Carrera 7 72-41");
  assert.match(ua ?? "", /ops@tukit\.co/);
});

test("nunca más de una petición por segundo, aunque lleguen juntas", async () => {
  const { buscador, llamadas } = armar(() => []);
  await Promise.all([buscador.buscar("Colegio Uno"), buscador.buscar("Colegio Cuatro"), buscador.buscar("Colegio Siete")]);
  assert.equal(llamadas.length, 3);
  for (let i = 1; i < llamadas.length; i++) {
    assert.ok(llamadas[i]!.t - llamadas[i - 1]!.t >= 1000, "intervalo menor a 1 s");
  }
});

test("la misma búsqueda sale una sola vez a la red, también la vacía", async () => {
  const { buscador, llamadas } = armar(() => []);
  await buscador.buscar("Colegio Uno");
  await buscador.buscar("  colegio  uno ");
  assert.equal(llamadas.length, 1);
});

test("dos visitantes con la misma búsqueda a la vez comparten una petición", async () => {
  const { buscador, llamadas } = armar(() => [CHAPINERO]);
  await Promise.all([buscador.buscar("Colegio Setenta"), buscador.buscar("Colegio Setenta")]);
  assert.equal(llamadas.length, 1);
});

test("la caché vence y la búsqueda vuelve a salir", async () => {
  const { buscador, llamadas, avanzar } = armar(() => [CHAPINERO]);
  await buscador.buscar("Colegio Setenta");
  avanzar(11 * 60_000);
  await buscador.buscar("Colegio Setenta");
  assert.equal(llamadas.length, 2);
});

test("un fallo de OSM es un error controlado y no se cachea", async () => {
  let falla = true;
  const { buscador, llamadas } = armar(() => (falla ? new Error("sin red") : [CHAPINERO]));
  await assert.rejects(buscador.buscar("Colegio Setenta"), (e: unknown) => {
    assert.ok(e instanceof ErrorBusqueda);
    assert.equal(e.estado, 502);
    return true;
  });
  falla = false;
  assert.equal((await buscador.buscar("Colegio Setenta")).length, 1);
  assert.equal(llamadas.length, 2);
});

test("una consulta muy corta no llega a OSM", async () => {
  const { buscador, llamadas } = armar(() => []);
  await assert.rejects(buscador.buscar("Ca"), (e: unknown) => e instanceof ErrorBusqueda && e.estado === 400);
  assert.equal(llamadas.length, 0);
});

test("con la cola llena responde 429 en vez de acumular esperas", async () => {
  const { buscador } = armar(() => []);
  const busquedas = ["Colegio Uno", "Colegio Cuatro", "Colegio Siete", "Colegio Nueve"].map((q) => buscador.buscar(q));
  const resultados = await Promise.allSettled(busquedas);
  const rechazadas = resultados.filter((r) => r.status === "rejected");
  assert.equal(rechazadas.length, 1);
  assert.equal(((rechazadas[0] as PromiseRejectedResult).reason as ErrorBusqueda).estado, 429);
});

function via(id: number, lat: string, lon: string, extra: Record<string, string> = {}) {
  return {
    osm_type: "way",
    osm_id: id,
    lat,
    lon,
    category: "highway",
    name: "Carrera 91",
    address: { road: "Carrera 91", suburb: "Localidad Fontibón", city: "Bogotá", ...extra },
  };
}

test("la misma calle del mismo barrio sale una sola vez aunque OSM la parta en tramos", async () => {
  const { leerCandidatos } = await import("../src/lib/direccion-osm.ts");
  const crudos = [1, 2, 3, 4, 5].map((i) => via(i, `4.67${i}`, `-74.12${i}`));
  const salida = leerCandidatos(crudos);
  assert.equal(salida.length, 1);
  assert.match(salida[0]!.secundario, /Fontibón/);
});

test("con número de casa la dirección es distinta y va primero", async () => {
  const { leerCandidatos } = await import("../src/lib/direccion-osm.ts");
  const salida = leerCandidatos([via(1, "4.671", "-74.121"), via(2, "4.672", "-74.122", { house_number: "19A-29" })]);
  assert.equal(salida.length, 2);
  assert.equal(salida[0]!.direccion, "Carrera 91 #19A-29");
});

test("la entrega es solo en Bogotá: límites duros y se descarta lo de fuera", async () => {
  const { leerCandidatos, parametrosDeBusqueda } = await import("../src/lib/direccion-osm.ts");
  assert.equal(parametrosDeBusqueda("calle 72").get("bounded"), "1");
  const medellin = { ...via(9, "6.2442", "-75.5812"), address: { road: "Carrera 91", city: "Medellín" } };
  assert.equal(leerCandidatos([medellin]).length, 0);
  const soacha = { ...via(8, "4.58", "-74.21"), address: { road: "Carrera 91", city: "Soacha" } };
  assert.equal(leerCandidatos([soacha]).length, 0);
});

const linea = (...p: [number, number][]) => ({ type: "LineString", coordinates: p });
const tramo = (id: number, road: string, geojson: unknown, extra: Record<string, string> = {}) => ({
  osm_type: "way", osm_id: id, lat: "4.667", lon: "-74.135", category: "highway", name: road, geojson,
  address: { road, suburb: "Localidad Fontibón", city: "Bogotá", ...extra },
});
const CRA91_BOSA = tramo(1, "Carrera 91", linea([-74.198, 4.62], [-74.198, 4.63]), { suburb: "Localidad Bosa" });
const CRA91_FONTIBON = tramo(2, "Carrera 91", linea([-74.135, 4.66], [-74.135, 4.67], [-74.135, 4.68]));
const CALLE19A = tramo(3, "Calle 19A", linea([-74.14, 4.667], [-74.13, 4.667]));

test("Carrera 91 #19A-29 se resuelve en el cruce con la Calle 19A, no en Bosa", async () => {
  const { candidatoDeCruce, parsearNomenclatura } = await import("../src/lib/direccion-osm.ts");
  const n = parsearNomenclatura("carrera 91 #19 A 29")!;
  const c = candidatoDeCruce([CRA91_BOSA, CRA91_FONTIBON], [CALLE19A], n, "carrera 91 #19 A 29")!;
  assert.equal(c.direccion, "Carrera 91 #19A-29");
  assert.match(c.completa, /Fontibón/);
  assert.equal(c.cruceCon, "Calle 19A");
  assert.equal(c.confirmarNumero, true);
  assert.ok(Math.abs(c.latitud - 4.667) < 0.001 && Math.abs(c.longitud + 74.135) < 0.001);
});

test("sin cruce cercano no hay candidato de cruce", async () => {
  const { candidatoDeCruce, parsearNomenclatura } = await import("../src/lib/direccion-osm.ts");
  const n = parsearNomenclatura("carrera 91 #19 A 29")!;
  assert.equal(candidatoDeCruce([CRA91_BOSA], [CALLE19A], n, "x"), null);
});

test("la vía de OSM como 'Avenida Calle 72' cuenta como Calle 72 y conserva la placa", async () => {
  const { candidatoDeCruce, parsearNomenclatura } = await import("../src/lib/direccion-osm.ts");
  const n = parsearNomenclatura("calle 72 # 10-34")!;
  const c72 = tramo(4, "Avenida Calle 72", linea([-74.06, 4.657], [-74.05, 4.657]), { suburb: "Localidad Chapinero" });
  const k10 = tramo(5, "Carrera 10", linea([-74.055, 4.65], [-74.055, 4.66]));
  const c = candidatoDeCruce([c72], [k10], n, "calle 72 # 10-34")!;
  assert.equal(c.direccion, "Calle 72 #10-34");
  assert.equal(c.cruceCon, "Carrera 10");
});

test("el buscador intenta el cruce primero y devuelve solo esa opción", async () => {
  const { buscador, llamadas } = armar((url) => (url.searchParams.get("street") === "Calle 19A" ? [CALLE19A] : [CRA91_BOSA, CRA91_FONTIBON]));
  const r = await buscador.buscar("carrera 91 #19 A 29");
  assert.equal(llamadas.length, 2);
  assert.equal(llamadas[0]!.url.searchParams.get("street"), "Carrera 91");
  assert.equal(llamadas[0]!.url.searchParams.get("bounded"), "1");
  assert.equal(r.length, 1);
  assert.equal(r[0]!.cruceCon, "Calle 19A");
});

test("si las vías no se tocan, cae a la búsqueda libre", async () => {
  const { buscador, llamadas } = armar((url) => (url.searchParams.has("street") ? [] : [CRA91_BOSA]));
  const r = await buscador.buscar("carrera 91 #19 A 29");
  assert.equal(llamadas.length, 5);
  assert.equal(llamadas[4]!.url.searchParams.get("q"), "carrera 91 19 A 29");
  assert.equal(r[0]!.cruceCon, undefined);
});

test("parsearNomenclatura entiende las formas en que se escribe una dirección", () => {
  const esperado = { via: "Carrera", numeroVia: "91", cruce: "19A", placa: "29" };
  for (const t of ["carrera 91 #19 A 29", "cra 91 19a-29", "Kr 91 # 19A - 29", "KR. 91 No. 19 a 29", "carrera 91 19A29x"]) {
    if (t.endsWith("x")) assert.equal(parsearNomenclatura(t), null);
    else assert.deepEqual(parsearNomenclatura(t), esperado, t);
  }
  assert.deepEqual(parsearNomenclatura("cl 72 10-34"), { via: "Calle", numeroVia: "72", cruce: "10", placa: "34" });
  assert.equal(parsearNomenclatura("dg 15 sur 3 40")?.via, "Diagonal");
  assert.equal(parsearNomenclatura("tv 60 112-10")?.via, "Transversal");
  assert.equal(parsearNomenclatura("av carrera 68 80-12")?.via, "Avenida Carrera");
  assert.equal(parsearNomenclatura("av 68 80-12")?.via, "Avenida");
  assert.deepEqual(parsearNomenclatura("carrera 91"), { via: "Carrera", numeroVia: "91", cruce: "", placa: "" });
  assert.equal(parsearNomenclatura("colegio san jose"), null);
});

test("formatearPlaca y formatearDireccion arman la línea colombiana", () => {
  assert.equal(formatearPlaca("19 A 29"), "#19A-29");
  assert.equal(formatearPlaca("29"), "#29");
  const zona = ["Villa Luz", "Localidad Engativá", "Bogotá"];
  const osm = formatearDireccion({ calle: "Carrera 91", numeroOsm: "19A-29", consulta: "cra 91 20-30", zona });
  assert.equal(osm.completa, "Carrera 91 #19A-29, Villa Luz, Localidad Engativá, Bogotá");
  assert.equal(osm.confirmarNumero, false);
  const padre = formatearDireccion({ calle: "Carrera 91", consulta: "cra 91 19a-29", zona });
  assert.equal(padre.direccion, "Carrera 91 #19A-29");
  assert.deepEqual([padre.confirmarNumero, padre.numeroDelPadre], [true, true]);
  const otra = formatearDireccion({ calle: "Carrera 910", consulta: "cra 91 19a-29", zona });
  assert.equal(otra.direccion, "Carrera 910");
  assert.deepEqual([otra.confirmarNumero, otra.numeroDelPadre], [true, false]);
});

test("leerCandidatos conserva el número del padre, muestra la línea completa y deduplica", () => {
  const calle = {
    osm_type: "way",
    lat: "4.70",
    lon: "-74.10",
    category: "highway",
    name: "Carrera 91",
    address: { road: "Carrera 91", neighbourhood: "Villa Luz", city_district: "Localidad Engativá", city: "Bogotá", postcode: "111041" },
  };
  const tramos = [{ ...calle, osm_id: 1 }, { ...calle, osm_id: 2, lat: "4.71" }];
  const salida = leerCandidatos(tramos, { consulta: "carrera 91 #19 A 29" });
  assert.equal(salida.length, 1);
  assert.equal(salida[0]!.completa, "Carrera 91 #19A-29, Villa Luz, Localidad Engativá, Bogotá, 111041");
  assert.equal(salida[0]!.principal, salida[0]!.completa);
  assert.equal(salida[0]!.confirmarNumero, true);
  assert.equal(salida[0]!.numeroDelPadre, true);
  assert.equal(leerCandidatos(tramos)[0]!.completa.startsWith("Carrera 91, Villa Luz"), true);
});
