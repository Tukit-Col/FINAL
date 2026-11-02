// Buscar la dirección del checkout en OpenStreetMap (ADR 0049), sin llave de Google.
//
// Por qué Nominatim y no Photon (photon.komoot.io): Photon sí permite autocompletar
// por tecla, pero responde con un formato propio (GeoJSON de "features") y casi
// nunca trae la localidad de Bogotá, que es lo que la logística necesita para
// agrupar el reparto. Nominatim devuelve el `address` completo, con "Localidad
// Chapinero" en `suburb`, y es el mismo servicio que ya usa el admin
// (`apps/admin/src/lib/geocodificador.ts`): una sola fuente, un solo contacto
// en el User-Agent, un solo conjunto de reglas. El costo es que su política
// PROHÍBE el autocompletado por tecla: la búsqueda es explícita (botón Buscar o
// Enter) y pasa por un proxy de servidor que cumple la política
// (operations.osmfoundation.org/policies/nominatim):
//   - como máximo UNA petición por segundo, para todos los visitantes juntos;
//   - User-Agent que identifica la app y trae un contacto real (sin contacto no
//     se consulta);
//   - caché corta: la misma búsqueda no vuelve a salir a la red;
//   - sesgo a Bogotá (viewbox + countrycodes=co) sin impedir Soacha o Chía.
//
// Este módulo no toca red, reloj ni disco por su cuenta: recibe `fetch`, el reloj
// y la espera. `app/api/direccion/buscar/route.ts` los conecta y las pruebas usan
// dobles. Sin imports a propósito: `node --test` corre este archivo tal cual.

/** Lo que el navegador necesita para mostrar un resultado y fijar el pin. */
export interface Candidato {
  id: string;
  /** Primera línea de la opción: la calle (con número si OSM lo trae) o el sitio. */
  principal: string;
  /** Segunda línea: barrio, localidad y ciudad, para distinguir homónimas. */
  secundario: string;
  /** La dirección normalizada que queda en el campo. */
  direccion: string;
  latitud: number;
  longitud: number;
  /** El subconjunto del `address` de OSM del que se derivan ciudad y localidad. */
  componentes: Record<string, string>;
}

export const INTERVALO_MS = 1100;
export const TTL_CACHE_MS = 10 * 60_000;
export const MINIMO_CARACTERES = 4;
export const MAXIMO_CARACTERES = 160;
export const MAXIMO_RESULTADOS = 5;
export const ATRIBUCION_OSM = "© OpenStreetMap";

// Bogotá y sus alrededores: izquierda, arriba, derecha, abajo (lon, lat, lon, lat).
// Es un SESGO (`bounded=0`), no una restricción.
const VIEWBOX_BOGOTA = "-74.35,4.95,-73.90,4.40";

// Colombia continental e insular. Es la misma caja que valida Comercio: un punto
// fuera de aquí es un homónimo de otro país y no se ofrece ni se acepta.
const CAJA_COLOMBIA = { sur: -4.3, norte: 13.6, oeste: -81.8, este: -66.8 };

export function dentroDeColombia(latitud: number, longitud: number): boolean {
  return (
    Number.isFinite(latitud) &&
    Number.isFinite(longitud) &&
    latitud >= CAJA_COLOMBIA.sur &&
    latitud <= CAJA_COLOMBIA.norte &&
    longitud >= CAJA_COLOMBIA.oeste &&
    longitud <= CAJA_COLOMBIA.este
  );
}

// Como se escribe una dirección en Colombia y como la entiende Nominatim: "Cra 7
// # 72-41" se vuelve "Carrera 7 72-41". Sin esto "Cra" no encuentra "Carrera".
const ABREVIATURAS: readonly (readonly [RegExp, string])[] = [
  [/\b(?:cra|crr|kra|kr|cr|carr)\b\.?/gi, "Carrera"],
  [/\b(?:cl|cll)\b\.?/gi, "Calle"],
  [/\b(?:av|avda|ave)\b\.?/gi, "Avenida"],
  [/\bak\b\.?/gi, "Avenida Carrera"],
  [/\bac\b\.?/gi, "Avenida Calle"],
  [/\b(?:dg|diag)\b\.?/gi, "Diagonal"],
  [/\b(?:tv|trv|transv)\b\.?/gi, "Transversal"],
];

/** La consulta lista para Nominatim: abreviaturas expandidas, sin "#" ni "No.". */
export function normalizarConsulta(texto: string): string {
  let q = texto.replace(/[#°º]/g, " ").replace(/\b(?:no|nro|num)\b\.?/gi, " ");
  for (const [patron, completo] of ABREVIATURAS) q = q.replace(patron, completo);
  return q.replace(/\s+/g, " ").trim().slice(0, MAXIMO_CARACTERES);
}

// Los campos del `address` de OSM de los que `direccionDesdeNominatim`
// (`@tukit/contrato`) saca ciudad, departamento y localidad.
const COMPONENTES_UTILES = [
  "state",
  "city",
  "town",
  "village",
  "municipality",
  "suburb",
  "city_district",
  "borough",
  "quarter",
] as const;

function texto(valor: unknown): string {
  return typeof valor === "string" ? valor.trim() : "";
}

/** Lee la respuesta JSON de Nominatim: descarta lo malformado y lo que cae fuera
 *  de Colombia, y repite ninguna dirección. */
export function leerCandidatos(cuerpo: unknown): Candidato[] {
  if (!Array.isArray(cuerpo)) return [];
  const vistos = new Set<string>();
  const salida: Candidato[] = [];
  for (const crudo of cuerpo) {
    if (typeof crudo !== "object" || crudo === null) continue;
    const item = crudo as Record<string, unknown>;
    const latitud = Number(item["lat"]);
    const longitud = Number(item["lon"]);
    if (!dentroDeColombia(latitud, longitud)) continue;

    const a = (typeof item["address"] === "object" && item["address"] !== null ? item["address"] : {}) as Record<
      string,
      unknown
    >;
    const calle = texto(a["road"]) || texto(a["pedestrian"]);
    const numero = texto(a["house_number"]);
    const nombre = texto(item["name"]);
    const base = calle ? (numero ? `${calle} # ${numero}` : calle) : nombre;
    // Un sitio (colegio, centro comercial) se muestra por su nombre, pero lo que
    // se guarda es su dirección: el repartidor busca una calle, no un letrero.
    const esSitio = !!nombre && nombre !== calle && item["category"] !== "highway";
    const direccion = base || texto(item["display_name"]).split(",")[0]?.trim() || "";
    if (!direccion) continue;

    const barrio = texto(a["neighbourhood"]);
    const secundario = [
      esSitio && calle ? direccion : "",
      /^upzs?\b/i.test(barrio) ? "" : barrio,
      texto(a["suburb"]),
      /^bogot[aá]/i.test(texto(a["city"])) ? "Bogotá" : texto(a["city"]) || texto(a["town"]) || texto(a["village"]),
    ]
      .filter(Boolean)
      .filter((parte, i, todas) => todas.indexOf(parte) === i)
      .join(", ");

    // `osm_id` llega como número: `texto` solo acepta cadenas.
    const id = `${texto(item["osm_type"])}${String(item["osm_id"] ?? "")}`;
    const clave = `${direccion}|${latitud.toFixed(4)}|${longitud.toFixed(4)}`;
    if (vistos.has(clave)) continue;
    vistos.add(clave);

    const componentes: Record<string, string> = {};
    for (const campo of COMPONENTES_UTILES) {
      const valor = texto(a[campo]);
      if (valor) componentes[campo] = valor;
    }
    salida.push({
      id: id || clave,
      principal: esSitio ? nombre : direccion,
      secundario,
      direccion,
      latitud,
      longitud,
      componentes,
    });
    if (salida.length >= MAXIMO_RESULTADOS) break;
  }
  return salida;
}

/** El User-Agent que exige la política: nombre de la app y cómo contactarnos. */
export function agenteUsuario(contacto: string): string {
  return `TukitWeb/0.1 (checkout; contacto: ${contacto})`;
}

export class ErrorBusqueda extends Error {
  // Campos explícitos y no propiedades de parámetro: `node --test` solo quita
  // tipos, no ejecuta esa sintaxis.
  estado: number;
  codigo: string;

  constructor(estado: number, codigo: string, mensaje: string) {
    super(mensaje);
    this.estado = estado;
    this.codigo = codigo;
  }
}

export interface OpcionesBuscador {
  /** Correo o URL de contacto que va en el User-Agent. Requerido por la política. */
  contacto: string;
  fetchFn: typeof fetch;
  esperar?: (ms: number) => Promise<void>;
  ahora?: () => number;
  intervaloMs?: number;
  ttlMs?: number;
  maxCache?: number;
  /** Cuántas búsquedas pueden estar esperando turno; las demás reciben 429. */
  maxEnCola?: number;
  timeoutMs?: number;
  url?: string;
}

export class BuscadorOsm {
  private ultimaPeticion = Number.NEGATIVE_INFINITY;
  // Cola de una sola fila: dos visitantes a la vez no se saltan el intervalo.
  private cola: Promise<unknown> = Promise.resolve();
  private esperando = 0;
  private readonly cache = new Map<string, { vence: number; candidatos: Candidato[] }>();
  private readonly enVuelo = new Map<string, Promise<Candidato[]>>();
  private readonly op: OpcionesBuscador;

  constructor(op: OpcionesBuscador) {
    this.op = op;
  }

  private ahora(): number {
    return (this.op.ahora ?? Date.now)();
  }

  async buscar(consulta: string): Promise<Candidato[]> {
    const q = normalizarConsulta(consulta);
    if (q.length < MINIMO_CARACTERES) {
      throw new ErrorBusqueda(400, "consulta_corta", `Escribe al menos ${MINIMO_CARACTERES} letras de la dirección.`);
    }
    const clave = q.toLowerCase();

    const guardado = this.cache.get(clave);
    if (guardado && guardado.vence > this.ahora()) return guardado.candidatos;
    // Dos visitantes buscando lo mismo a la vez comparten una sola petición.
    const enCurso = this.enVuelo.get(clave);
    if (enCurso) return enCurso;

    if (this.esperando >= (this.op.maxEnCola ?? 3)) {
      throw new ErrorBusqueda(429, "buscador_ocupado", "El buscador está ocupado. Intenta de nuevo en unos segundos.");
    }
    this.esperando += 1;
    const turno = this.cola.then(() => this.consultar(q, clave)).finally(() => {
      this.esperando -= 1;
      this.enVuelo.delete(clave);
    });
    this.cola = turno.catch(() => undefined);
    this.enVuelo.set(clave, turno);
    return turno;
  }

  private async consultar(q: string, clave: string): Promise<Candidato[]> {
    const intervalo = this.op.intervaloMs ?? INTERVALO_MS;
    const espera = this.ultimaPeticion + intervalo - this.ahora();
    if (espera > 0) await (this.op.esperar ?? ((ms) => new Promise<void>((r) => setTimeout(r, ms))))(espera);
    this.ultimaPeticion = this.ahora();

    const url = new URL(this.op.url ?? "https://nominatim.openstreetmap.org/search");
    url.searchParams.set("format", "jsonv2");
    url.searchParams.set("addressdetails", "1");
    url.searchParams.set("limit", String(MAXIMO_RESULTADOS + 3));
    url.searchParams.set("countrycodes", "co");
    url.searchParams.set("accept-language", "es");
    url.searchParams.set("viewbox", VIEWBOX_BOGOTA);
    url.searchParams.set("q", q);

    let cuerpo: unknown;
    try {
      const respuesta = await this.op.fetchFn(url, {
        headers: { "User-Agent": agenteUsuario(this.op.contacto), Accept: "application/json" },
        signal: AbortSignal.timeout(this.op.timeoutMs ?? 6000),
      });
      if (!respuesta.ok) throw new Error(`Nominatim respondió ${respuesta.status}`);
      cuerpo = await respuesta.json();
    } catch {
      // Sin red, tiempo agotado, 429 o 5xx de OSM: el checkout sigue con texto
      // libre. No se guarda en caché para que el siguiente intento sí salga.
      throw new ErrorBusqueda(502, "buscador_no_disponible", "No pudimos consultar el mapa ahora.");
    }

    const candidatos = leerCandidatos(cuerpo);
    // También se guarda "sin resultados": repetir la misma búsqueda vacía no
    // debe volver a pegarle a OSM.
    this.cache.set(clave, { vence: this.ahora() + (this.op.ttlMs ?? TTL_CACHE_MS), candidatos });
    while (this.cache.size > (this.op.maxCache ?? 200)) {
      const masVieja = this.cache.keys().next().value;
      if (masVieja === undefined) break;
      this.cache.delete(masVieja);
    }
    return candidatos;
  }
}
