// Buscar la dirección del checkout en OpenStreetMap (Nominatim), sin llave de Google.
//
// Decisiones:
// - Nominatim y no Photon: Photon permite autocompletar por tecla pero casi nunca trae la localidad de
//   Bogotá, que la logística necesita para agrupar el reparto; Nominatim devuelve el `address` completo
//   y es el mismo servicio que usa el admin (`apps/admin/src/lib/geocodificador.ts`).
// - Su política prohíbe el autocompletado por tecla: la búsqueda es explícita y pasa por un proxy de
//   servidor que cumple como máximo una petición por segundo para todos los visitantes juntos, un
//   User-Agent con contacto real (sin contacto no se consulta), caché corta y sesgo a Bogotá
//   (viewbox y `countrycodes=co`) sin impedir Soacha o Chía.
// - No toca red, reloj ni disco por su cuenta: recibe `fetch`, el reloj y la espera, y no importa nada,
//   para que `node --test` lo corra tal cual.

export interface Candidato {
  id: string;
  principal: string;
  secundario: string;
  direccion: string;
  completa: string;
  confirmarNumero: boolean;
  numeroDelPadre: boolean;
  latitud: number;
  longitud: number;
  cruceCon?: string;
  componentes: Record<string, string>;
}

export const INTERVALO_MS = 1100;
export const TTL_CACHE_MS = 10 * 60_000;
export const MINIMO_CARACTERES = 4;
export const MAXIMO_CARACTERES = 160;
export const MAXIMO_RESULTADOS = 5;
export const ATRIBUCION_OSM = "© OpenStreetMap";

const VIEWBOX_BOGOTA = "-74.35,4.95,-73.90,4.40";

export function dentroDeBogota(latitud: number, longitud: number): boolean {
  return latitud >= 4.4 && latitud <= 4.95 && longitud >= -74.35 && longitud <= -73.9;
}

export interface OpcionesConsulta {
  consulta?: string;
}

function parametrosBase(limite: number): URLSearchParams {
  const p = new URLSearchParams();
  p.set("format", "jsonv2");
  p.set("addressdetails", "1");
  p.set("limit", String(limite));
  p.set("countrycodes", "co");
  p.set("accept-language", "es");
  p.set("viewbox", VIEWBOX_BOGOTA);
  p.set("bounded", "1");
  return p;
}

export function parametrosDeBusqueda(q: string): URLSearchParams {
  const p = parametrosBase(MAXIMO_RESULTADOS + 3);
  p.set("q", q);
  return p;
}

export function parametrosDeVia(via: string): URLSearchParams {
  const p = parametrosBase(40);
  p.set("street", via);
  p.set("city", "Bogotá");
  p.set("polygon_geojson", "1");
  return p;
}

function sinTildes(t: string): string {
  return t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
}

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

const ABREVIATURAS: readonly (readonly [RegExp, string])[] = [
  [/\b(?:cra|crr|kra|kr|cr|carr)\b\.?/gi, "Carrera"],
  [/\b(?:cl|cll)\b\.?/gi, "Calle"],
  [/\b(?:av|avda|ave)\b\.?/gi, "Avenida"],
  [/\bak\b\.?/gi, "Avenida Carrera"],
  [/\bac\b\.?/gi, "Avenida Calle"],
  [/\b(?:dg|diag)\b\.?/gi, "Diagonal"],
  [/\b(?:tv|trv|transv)\b\.?/gi, "Transversal"],
];

export function normalizarConsulta(texto: string): string {
  let q = texto.replace(/[#°º]/g, " ").replace(/\b(?:no|nro|num)\b\.?/gi, " ");
  for (const [patron, completo] of ABREVIATURAS) q = q.replace(patron, completo);
  return q.replace(/\s+/g, " ").trim().slice(0, MAXIMO_CARACTERES);
}

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

export interface Nomenclatura {
  via: string;
  numeroVia: string;
  cruce: string;
  placa: string;
}

const TIPOS_VIA: Record<string, string> = {
  cra: "Carrera", crr: "Carrera", kra: "Carrera", kr: "Carrera", cr: "Carrera", carr: "Carrera", carrera: "Carrera",
  cl: "Calle", cll: "Calle", calle: "Calle",
  av: "Avenida", avda: "Avenida", avenida: "Avenida",
  ak: "Avenida Carrera", ac: "Avenida Calle",
  dg: "Diagonal", diag: "Diagonal", diagonal: "Diagonal",
  tv: "Transversal", trv: "Transversal", transv: "Transversal", transversal: "Transversal",
};
const ALTERNATIVA_TIPOS = Object.keys(TIPOS_VIA).sort((a, b) => b.length - a.length).join("|");
const PATRON_NOMENCLATURA = new RegExp(
  `^(${ALTERNATIVA_TIPOS})(?:\\s+(carrera|calle|cra|cl))?\\s*(\\d+)(?:\\s*([a-z])(?![a-z]))?(?:\\s+bis)?(?:\\s+(?:sur|norte|este|oeste))?` +
    `(?:\\s+(\\d+)(?:\\s*([a-z])(?![a-z]))?\\s*-?\\s*(\\d+))?\\s*$`,
);

export function parsearNomenclatura(texto: string): Nomenclatura | null {
  const t = sinTildes(texto)
    .replace(/[#°º.,]/g, " ")
    .replace(/\b(?:no|nro|num|n)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const m = PATRON_NOMENCLATURA.exec(t);
  if (!m) return null;
  const base = TIPOS_VIA[m[1]!]!;
  const segunda = m[2] ? TIPOS_VIA[m[2]] : "";
  const via = segunda && base === "Avenida" ? `${base} ${segunda}` : base;
  return {
    via,
    numeroVia: `${m[3]}${(m[4] ?? "").toUpperCase()}`,
    cruce: m[5] ? `${m[5]}${(m[6] ?? "").toUpperCase()}` : "",
    placa: m[7] ?? "",
  };
}

export function formatearPlaca(crudo: string): string {
  const t = sinTildes(crudo).replace(/[#.]/g, " ").replace(/\s+/g, " ").trim().toUpperCase();
  const m = /^(\d+)\s*([A-Z])?\s*[-\s]\s*(\d+)$/.exec(t);
  if (m) return `#${m[1]}${m[2] ?? ""}-${m[3]}`;
  return t ? `#${t}` : "";
}

function mismaVia(calleOsm: string, n: Nomenclatura): boolean {
  const osm = sinTildes(calleOsm).replace(/\s+/g, "");
  const propia = sinTildes(`${n.via}${n.numeroVia}`).replace(/\s+/g, "");
  return osm.startsWith(propia) && !/\d/.test(osm.charAt(propia.length));
}

export interface PartesDireccion {
  calle: string;
  numeroOsm?: string;
  consulta?: string;
  zona?: readonly string[];
}

export interface DireccionFormateada {
  direccion: string;
  completa: string;
  confirmarNumero: boolean;
  numeroDelPadre: boolean;
}

export function formatearDireccion(partes: PartesDireccion): DireccionFormateada {
  const zona = (partes.zona ?? []).filter(Boolean).filter((p, i, todas) => todas.findIndex((q) => sinTildes(q) === sinTildes(p)) === i);
  let direccion = partes.calle;
  let confirmarNumero = false;
  let numeroDelPadre = false;
  if (partes.calle) {
    if (partes.numeroOsm) {
      direccion = `${partes.calle} ${formatearPlaca(partes.numeroOsm)}`;
    } else {
      confirmarNumero = true;
      const propia = partes.consulta ? parsearNomenclatura(partes.consulta) : null;
      if (propia && propia.cruce && propia.placa && mismaVia(partes.calle, propia)) {
        direccion = `${partes.calle} #${propia.cruce}-${propia.placa}`;
        numeroDelPadre = true;
      }
    }
  }
  return { direccion, completa: [direccion, ...zona].filter(Boolean).join(", "), confirmarNumero, numeroDelPadre };
}

export function leerCandidatos(cuerpo: unknown, opciones: OpcionesConsulta = {}): Candidato[] {
  if (!Array.isArray(cuerpo)) return [];
  const vistos = new Set<string>();
  const salida: { candidato: Candidato; puntaje: number }[] = [];
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
    const numeroOsm = texto(a["house_number"]);
    const numero = numeroOsm;
    const nombre = texto(item["name"]);
    const barrio = texto(a["neighbourhood"]);
    const ciudad = /^bogot[aá]/i.test(texto(a["city"])) ? "Bogotá" : texto(a["city"]) || texto(a["town"]) || texto(a["village"]);
    const zona = [
      /^upzs?\b/i.test(barrio) ? "" : barrio,
      texto(a["quarter"]),
      texto(a["suburb"]),
      texto(a["city_district"]),
      ciudad,
      texto(a["postcode"]),
    ].filter(Boolean);
    const f = calle
      ? formatearDireccion({ calle, numeroOsm, consulta: opciones.consulta, zona })
      : { direccion: "", completa: "", confirmarNumero: false, numeroDelPadre: false };
    const esSitio = !!nombre && nombre !== calle && item["category"] !== "highway";
    const direccion = f.direccion || nombre || texto(item["display_name"]).split(",")[0]?.trim() || "";
    if (!direccion) continue;
    const secundario = zona.filter((parte, i, todas) => todas.indexOf(parte) === i).filter((p) => p !== texto(a["postcode"])).join(", ");
    const completa = f.completa || [direccion, ...zona].join(", ");

    const id = `${texto(item["osm_type"])}${String(item["osm_id"] ?? "")}`;
    if (!dentroDeBogota(latitud, longitud) || (ciudad && ciudad !== "Bogotá")) continue;
    const clave = sinTildes(completa);
    if (vistos.has(clave)) continue;
    vistos.add(clave);

    const componentes: Record<string, string> = {};
    for (const campo of COMPONENTES_UTILES) {
      const valor = texto(a[campo]);
      if (valor) componentes[campo] = valor;
    }
    salida.push({
      candidato: {
        id: id || clave,
        principal: esSitio ? nombre : completa,
        secundario,
        direccion,
        completa: esSitio ? `${nombre}, ${completa}` : completa,
        confirmarNumero: f.confirmarNumero,
        numeroDelPadre: f.numeroDelPadre,
        latitud,
        longitud,
        componentes,
      },
      puntaje: numero ? 1 : 0,
    });
  }
  return salida
    .sort((a, b) => b.puntaje - a.puntaje)
    .slice(0, MAXIMO_RESULTADOS)
    .map((x) => x.candidato);
}

export type Punto = readonly [number, number];

export const TOLERANCIA_CRUCE_M = 300;

const M_POR_GRADO = 111_320;

export function trazados(geojson: unknown): Punto[][] {
  if (typeof geojson !== "object" || geojson === null) return [];
  const g = geojson as { type?: unknown; coordinates?: unknown };
  const lineas = g.type === "LineString" ? [g.coordinates] : g.type === "MultiLineString" ? g.coordinates : [];
  if (!Array.isArray(lineas)) return [];
  const salida: Punto[][] = [];
  for (const linea of lineas) {
    if (!Array.isArray(linea)) continue;
    const puntos: Punto[] = [];
    for (const p of linea) {
      if (Array.isArray(p) && Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1]))) puntos.push([Number(p[0]), Number(p[1])]);
    }
    if (puntos.length >= 2) salida.push(puntos);
  }
  return salida;
}

function alSegmento(p: Punto, a: Punto, b: Punto): { metros: number; punto: Punto } {
  const k = Math.cos((p[1] * Math.PI) / 180);
  const ax = (a[0] - p[0]) * k, ay = a[1] - p[1];
  const bx = (b[0] - p[0]) * k, by = b[1] - p[1];
  const dx = bx - ax, dy = by - ay;
  const largo2 = dx * dx + dy * dy;
  const t = largo2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / largo2));
  const cx = ax + t * dx, cy = ay + t * dy;
  return { metros: Math.hypot(cx, cy) * M_POR_GRADO, punto: [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])] };
}

function interseccion(p1: Punto, p2: Punto, p3: Punto, p4: Punto): Punto | null {
  const d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0]);
  if (d === 0) return null;
  const t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d;
  const u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d;
  if (t < 0 || t > 1 || u < 0 || u > 1) return null;
  return [p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])];
}

export function puntoMasCercano(a: readonly (readonly Punto[])[], b: readonly (readonly Punto[])[]): { metros: number; punto: Punto } | null {
  let mejor = null as { metros: number; punto: Punto } | null;
  const probar = (lineasP: readonly (readonly Punto[])[], lineasQ: readonly (readonly Punto[])[], deA: boolean) => {
    for (const lp of lineasP) for (const v of lp) for (const lq of lineasQ) for (let i = 0; i + 1 < lq.length; i++) {
      const r = alSegmento(v, lq[i]!, lq[i + 1]!);
      if (mejor && r.metros >= mejor.metros) continue;
      mejor = { metros: r.metros, punto: deA ? v : r.punto };
    }
  };
  for (const la of a) for (let i = 0; i + 1 < la.length; i++) for (const lb of b) for (let j = 0; j + 1 < lb.length; j++) {
    const x = interseccion(la[i]!, la[i + 1]!, lb[j]!, lb[j + 1]!);
    if (x) return { metros: 0, punto: x };
  }
  probar(a, b, true);
  probar(b, a, false);
  return mejor;
}

function unir(a: unknown, b: unknown): unknown[] {
  return [...(Array.isArray(a) ? a : []), ...(Array.isArray(b) ? b : [])];
}

export function viaQueCruza(n: Nomenclatura): string | null {
  if (!n.cruce) return null;
  if (/carrera$/i.test(n.via)) return `Calle ${n.cruce}`;
  if (/calle$/i.test(n.via)) return `Carrera ${n.cruce}`;
  return null;
}

const sinAvenida = (t: string) => t.replace(/^avenida\s+/i, "");

function tramosDe(cuerpo: unknown, via: string): { item: Record<string, unknown>; lineas: Punto[][] }[] {
  if (!Array.isArray(cuerpo)) return [];
  const n = parsearNomenclatura(sinAvenida(via));
  const salida: { item: Record<string, unknown>; lineas: Punto[][] }[] = [];
  for (const crudo of cuerpo) {
    if (typeof crudo !== "object" || crudo === null) continue;
    const item = crudo as Record<string, unknown>;
    const a = (typeof item["address"] === "object" && item["address"] !== null ? item["address"] : {}) as Record<string, unknown>;
    const calle = sinAvenida(texto(a["road"]) || texto(item["name"]));
    const lineas = trazados(item["geojson"]);
    if (n && lineas.length > 0 && mismaVia(calle, n)) salida.push({ item, lineas });
  }
  return salida;
}

export function candidatoDeCruce(cuerpoVia: unknown, cuerpoCruce: unknown, n: Nomenclatura, consulta: string): Candidato | null {
  const cruzante = viaQueCruza(n);
  if (!cruzante) return null;
  const propias = tramosDe(cuerpoVia, `${n.via} ${n.numeroVia}`);
  const otras = tramosDe(cuerpoCruce, cruzante);
  if (propias.length === 0 || otras.length === 0) return null;
  const todasOtras = otras.flatMap((o) => o.lineas);
  let mejor: { tramo: (typeof propias)[number]; metros: number; punto: Punto } | null = null;
  for (const tramo of propias) {
    const r = puntoMasCercano(tramo.lineas, todasOtras);
    if (r && (!mejor || r.metros < mejor.metros)) mejor = { tramo, metros: r.metros, punto: r.punto };
  }
  if (!mejor || mejor.metros > TOLERANCIA_CRUCE_M) return null;
  const direccionOsm = (mejor.tramo.item["address"] ?? {}) as Record<string, unknown>;
  const sintetico = {
    ...mejor.tramo.item,
    lat: String(mejor.punto[1]),
    lon: String(mejor.punto[0]),
    name: "",
    geojson: undefined,
    address: { ...direccionOsm, road: `${n.via} ${n.numeroVia}`, house_number: undefined },
  };
  const c = leerCandidatos([sintetico], { consulta })[0];
  if (!c) return null;
  return { ...c, id: `cruce-${c.id}`, cruceCon: cruzante, confirmarNumero: true };
}

export function agenteUsuario(contacto: string): string {
  return `TukitWeb/0.1 (checkout; contacto: ${contacto})`;
}

export class ErrorBusqueda extends Error {
  estado: number;
  codigo: string;

  constructor(estado: number, codigo: string, mensaje: string) {
    super(mensaje);
    this.estado = estado;
    this.codigo = codigo;
  }
}

export interface OpcionesBuscador {
  contacto: string;
  fetchFn: typeof fetch;
  esperar?: (ms: number) => Promise<void>;
  ahora?: () => number;
  intervaloMs?: number;
  ttlMs?: number;
  maxCache?: number;
  maxEnCola?: number;
  timeoutMs?: number;
  url?: string;
}

export class BuscadorOsm {
  private ultimaPeticion = Number.NEGATIVE_INFINITY;
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

  async buscar(consulta: string, opciones: OpcionesConsulta = {}): Promise<Candidato[]> {
    const original = consulta;
    const q = normalizarConsulta(consulta);
    if (q.length < MINIMO_CARACTERES) {
      throw new ErrorBusqueda(400, "consulta_corta", `Escribe al menos ${MINIMO_CARACTERES} letras de la dirección.`);
    }
    const clave = q.toLowerCase();

    const guardado = this.cache.get(clave);
    if (guardado && guardado.vence > this.ahora()) return guardado.candidatos;
    const enCurso = this.enVuelo.get(clave);
    if (enCurso) return enCurso;

    if (this.esperando >= (this.op.maxEnCola ?? 3)) {
      throw new ErrorBusqueda(429, "buscador_ocupado", "El buscador está ocupado. Intenta de nuevo en unos segundos.");
    }
    this.esperando += 1;
    const turno = this.cola.then(() => this.consultar(q, clave, { ...opciones, consulta: original })).finally(() => {
      this.esperando -= 1;
      this.enVuelo.delete(clave);
    });
    this.cola = turno.catch(() => undefined);
    this.enVuelo.set(clave, turno);
    return turno;
  }

  private async pedir(parametros: URLSearchParams): Promise<unknown> {
    const intervalo = this.op.intervaloMs ?? INTERVALO_MS;
    const espera = this.ultimaPeticion + intervalo - this.ahora();
    if (espera > 0) await (this.op.esperar ?? ((ms) => new Promise<void>((r) => setTimeout(r, ms))))(espera);
    this.ultimaPeticion = this.ahora();

    const url = new URL(this.op.url ?? "https://nominatim.openstreetmap.org/search");
    url.search = parametros.toString();
    try {
      const respuesta = await this.op.fetchFn(url, {
        headers: { "User-Agent": agenteUsuario(this.op.contacto), Accept: "application/json" },
        signal: AbortSignal.timeout(this.op.timeoutMs ?? 6000),
      });
      if (!respuesta.ok) throw new Error(`Nominatim respondió ${respuesta.status}`);
      return await respuesta.json();
    } catch {
      throw new ErrorBusqueda(502, "buscador_no_disponible", "No pudimos consultar el mapa ahora.");
    }
  }

  private async consultar(q: string, clave: string, opciones: OpcionesConsulta): Promise<Candidato[]> {
    const guardar = (candidatos: Candidato[]) => {
      this.guardar(clave, candidatos);
      return candidatos;
    };
    const n = opciones.consulta ? parsearNomenclatura(opciones.consulta) : null;
    const cruzante = n ? viaQueCruza(n) : null;
    if (n && cruzante) {
      const propia = `${n.via} ${n.numeroVia}`;
      let cuerpoVia = await this.pedir(parametrosDeVia(propia));
      let cuerpoCruce = await this.pedir(parametrosDeVia(cruzante));
      let cruce = candidatoDeCruce(cuerpoVia, cuerpoCruce, n, opciones.consulta ?? "");
      if (!cruce && !/^avenida/i.test(propia)) {
        const avenidaVia = await this.pedir(parametrosDeVia(`Avenida ${propia}`));
        const avenidaCruce = await this.pedir(parametrosDeVia(`Avenida ${cruzante}`));
        cuerpoVia = unir(cuerpoVia, avenidaVia);
        cuerpoCruce = unir(cuerpoCruce, avenidaCruce);
        cruce = candidatoDeCruce(cuerpoVia, cuerpoCruce, n, opciones.consulta ?? "");
      }
      if (cruce) return guardar([cruce]);
    }
    const cuerpo = await this.pedir(parametrosDeBusqueda(q));
    return guardar(leerCandidatos(cuerpo, opciones));
  }

  private guardar(clave: string, candidatos: Candidato[]): void {
    this.cache.set(clave, { vence: this.ahora() + (this.op.ttlMs ?? TTL_CACHE_MS), candidatos });
    while (this.cache.size > (this.op.maxCache ?? 200)) {
      const masVieja = this.cache.keys().next().value;
      if (masVieja === undefined) break;
      this.cache.delete(masVieja);
    }
  }
}
