// La politica de Nominatim hecha prueba: una peticion por segundo, User-Agent con
// contacto, cache (tambien negativa), tope por llamada y descarte de homonimos
// fuera de Colombia.
//
// Correr:  node --test test/geocodificador.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  agenteUsuario,
  claveDireccion,
  Geocodificador,
  leerRespuestaNominatim,
  type EntradaCache,
} from "../src/lib/geocodificador.ts";

const BOGOTA = [{ lat: "4.6097", lon: "-74.0817" }];

function armar(respuestas: (url: URL) => unknown | Error, opciones: { maxNuevas?: number } = {}) {
  const llamadas: { url: URL; ua: string | null; t: number }[] = [];
  let reloj = 1_000_000;
  const cache: Record<string, EntradaCache> = {};
  let escrituras = 0;
  const geo = new Geocodificador({
    contacto: "ops@tukit.co",
    maxNuevas: opciones.maxNuevas,
    ahora: () => reloj,
    esperar: async (ms) => {
      reloj += ms;
    },
    almacen: {
      leer: async () => structuredClone(cache),
      escribir: async (d) => {
        escrituras += 1;
        Object.assign(cache, d);
      },
    },
    fetchFn: (async (url: URL, init: RequestInit) => {
      llamadas.push({ url, ua: (init.headers as Record<string, string>)["User-Agent"] ?? null, t: reloj });
      const r = respuestas(url);
      if (r instanceof Error) throw r;
      return { ok: true, status: 200, json: async () => r } as Response;
    }) as unknown as typeof fetch,
  });
  return { geo, llamadas, cache, escrituras: () => escrituras };
}

const dir = (direccion: string) => ({ direccion, ciudad: "Bogotá", departamento: "Cundinamarca" });

test("la clave ignora tildes, mayusculas y espacios sobrantes", () => {
  assert.equal(claveDireccion(dir("  Cra 7  # 8-9 ")), claveDireccion(dir("cra 7 # 8-9")));
  assert.equal(claveDireccion({ ...dir("x"), ciudad: "BOGOTÁ" }), claveDireccion({ ...dir("x"), ciudad: "bogota" }));
});

test("el User-Agent trae el contacto", () => {
  assert.match(agenteUsuario("ops@tukit.co"), /ops@tukit\.co/);
});

test("una direccion nueva se consulta una vez y la segunda sale de la cache", async () => {
  const { geo, llamadas } = armar(() => BOGOTA);
  const a = await geo.resolver([dir("Calle 1 # 2-3")]);
  assert.deepEqual([...a.values()], [{ lat: 4.6097, lon: -74.0817 }]);
  await geo.resolver([dir("calle 1 # 2-3")]);
  assert.equal(llamadas.length, 1);
  assert.equal(llamadas[0].ua, agenteUsuario("ops@tukit.co"));
  assert.equal(llamadas[0].url.searchParams.get("countrycodes"), "co");
});

test("nunca dos peticiones con menos de un segundo de diferencia", async () => {
  const { geo, llamadas } = armar(() => BOGOTA);
  await geo.resolver([dir("A 1"), dir("B 2"), dir("C 3")]);
  assert.equal(llamadas.length, 3);
  for (let i = 1; i < llamadas.length; i++) assert.ok(llamadas[i].t - llamadas[i - 1].t >= 1000);
});

test("lo que no encuentra se guarda como fallo y no se vuelve a pedir", async () => {
  const { geo, llamadas, cache } = armar(() => []);
  const r = await geo.resolver([dir("Inexistente 999")]);
  assert.deepEqual([...r.values()], [null]);
  assert.equal(Object.values(cache)[0].lat, null);
  await geo.resolver([dir("Inexistente 999")]);
  assert.equal(llamadas.length, 1);
});

test("el tope por llamada deja el resto pendiente, sin consultarlo", async () => {
  const { geo, llamadas } = armar(() => BOGOTA, { maxNuevas: 2 });
  const r = await geo.resolver([dir("A 1"), dir("B 2"), dir("C 3")]);
  assert.equal(llamadas.length, 2);
  assert.deepEqual([...r.values()].filter((v) => v === "pendiente").length, 1);
});

test("un error de red no se guarda: queda pendiente para la proxima", async () => {
  const { geo, cache, escrituras } = armar(() => new Error("sin red"));
  const r = await geo.resolver([dir("A 1")]);
  assert.deepEqual([...r.values()], ["pendiente"]);
  assert.deepEqual(cache, {});
  assert.equal(escrituras(), 0);
});

test("un homonimo fuera de Colombia se descarta", () => {
  assert.equal(leerRespuestaNominatim([{ lat: "40.4", lon: "-3.7" }]), null);
  assert.equal(leerRespuestaNominatim([]), null);
  assert.equal(leerRespuestaNominatim([{ lat: "x", lon: "y" }]), null);
  assert.deepEqual(leerRespuestaNominatim(BOGOTA), { lat: 4.6097, lon: -74.0817 });
});

test("dos llamadas simultaneas se serializan y respetan el intervalo", async () => {
  const { geo, llamadas } = armar(() => BOGOTA);
  await Promise.all([geo.resolver([dir("A 1")]), geo.resolver([dir("B 2")])]);
  assert.equal(llamadas.length, 2);
  assert.ok(llamadas[1].t - llamadas[0].t >= 1000);
});
