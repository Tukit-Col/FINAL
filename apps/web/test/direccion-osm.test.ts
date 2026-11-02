// La búsqueda de direcciones en OpenStreetMap hecha prueba: la política del
// Nominatim público (una petición por segundo, User-Agent con contacto, caché,
// sesgo a Bogotá), el descarte de homónimos fuera de Colombia y que un fallo del
// servicio sea un error controlado y no un cuelgue del pago.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/direccion-osm.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { direccionDesdeNominatim } from "../../../libs/ts/tukit-contrato/src/localidades.ts";
import {
  agenteUsuario,
  BuscadorOsm,
  ErrorBusqueda,
  leerCandidatos,
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
  assert.equal(unico?.direccion, "Calle 72 # 10-34");
  assert.equal(unico?.latitud, 4.6518184);
  assert.equal(unico?.longitud, -74.0510026);
  // El barrio "UPZs de Bogotá" es ruido de OSM: no se muestra.
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
  // Fuera de Bogotá no hay localidad, aunque OSM traiga un suburb.
  assert.deepEqual(direccionDesdeNominatim({ town: "Chía", state: "Cundinamarca", suburb: "Fonqueta" }), {
    ciudad: "Chía",
    departamento: "Cundinamarca",
    localidad: "",
  });
  // Sin localidad reconocible, la elige el acudiente.
  assert.equal(direccionDesdeNominatim({ city: "Bogotá ciudad", state: "Bogotá, Distrito Capital" }).localidad, "");
  assert.equal(direccionDesdeNominatim(null).ciudad, "");
});

test("la consulta sesga a Bogotá, pide Colombia y manda el contacto", async () => {
  const { buscador, llamadas } = armar(() => [CHAPINERO]);
  const r = await buscador.buscar("Cra 7 # 72-41");
  assert.equal(r.length, 1);
  const { url, ua } = llamadas[0]!;
  assert.equal(url.searchParams.get("countrycodes"), "co");
  assert.equal(url.searchParams.get("viewbox"), "-74.35,4.95,-73.90,4.40");
  assert.equal(url.searchParams.get("bounded"), null);
  assert.equal(url.searchParams.get("q"), "Carrera 7 72-41");
  assert.match(ua ?? "", /ops@tukit\.co/);
});

test("nunca más de una petición por segundo, aunque lleguen juntas", async () => {
  const { buscador, llamadas } = armar(() => []);
  await Promise.all([buscador.buscar("Calle 1 2-3"), buscador.buscar("Calle 4 5-6"), buscador.buscar("Calle 7 8-9")]);
  assert.equal(llamadas.length, 3);
  for (let i = 1; i < llamadas.length; i++) {
    assert.ok(llamadas[i]!.t - llamadas[i - 1]!.t >= 1000, "intervalo menor a 1 s");
  }
});

test("la misma búsqueda sale una sola vez a la red, también la vacía", async () => {
  const { buscador, llamadas } = armar(() => []);
  await buscador.buscar("Calle 1 2-3");
  await buscador.buscar("  calle 1  2-3 ");
  assert.equal(llamadas.length, 1);
});

test("dos visitantes con la misma búsqueda a la vez comparten una petición", async () => {
  const { buscador, llamadas } = armar(() => [CHAPINERO]);
  await Promise.all([buscador.buscar("Calle 72 10-34"), buscador.buscar("Calle 72 10-34")]);
  assert.equal(llamadas.length, 1);
});

test("la caché vence y la búsqueda vuelve a salir", async () => {
  const { buscador, llamadas, avanzar } = armar(() => [CHAPINERO]);
  await buscador.buscar("Calle 72 10-34");
  avanzar(11 * 60_000);
  await buscador.buscar("Calle 72 10-34");
  assert.equal(llamadas.length, 2);
});

test("un fallo de OSM es un error controlado y no se cachea", async () => {
  let falla = true;
  const { buscador, llamadas } = armar(() => (falla ? new Error("sin red") : [CHAPINERO]));
  await assert.rejects(buscador.buscar("Calle 72 10-34"), (e: unknown) => {
    assert.ok(e instanceof ErrorBusqueda);
    assert.equal(e.estado, 502);
    return true;
  });
  falla = false;
  assert.equal((await buscador.buscar("Calle 72 10-34")).length, 1);
  assert.equal(llamadas.length, 2);
});

test("una consulta muy corta no llega a OSM", async () => {
  const { buscador, llamadas } = armar(() => []);
  await assert.rejects(buscador.buscar("Ca"), (e: unknown) => e instanceof ErrorBusqueda && e.estado === 400);
  assert.equal(llamadas.length, 0);
});

test("con la cola llena responde 429 en vez de acumular esperas", async () => {
  const { buscador } = armar(() => []);
  const busquedas = ["Calle 1 2-3", "Calle 4 5-6", "Calle 7 8-9", "Calle 9 9-9"].map((q) => buscador.buscar(q));
  const resultados = await Promise.allSettled(busquedas);
  const rechazadas = resultados.filter((r) => r.status === "rejected");
  assert.equal(rechazadas.length, 1);
  assert.equal(((rechazadas[0] as PromiseRejectedResult).reason as ErrorBusqueda).estado, 429);
});
