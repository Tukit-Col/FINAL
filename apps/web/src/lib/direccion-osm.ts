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
  /** La dirección normalizada que queda en el campo ("Carrera 91 #19A-29"). */
  direccion: string;
  /** La dirección completa en una línea, estilo colombiano:
   *  "Carrera 91 #19A-29, Barrio, Localidad, Bogotá". */
  completa: string;
  /** OSM solo resolvió la calle: el número no es de OSM y hay que confirmarlo. */
  confirmarNumero: boolean;
  /** El número que muestra es el que escribió el padre (OSM no lo traía). */
  numeroDelPadre: boolean;
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
// Por omisión es un SESGO (`bounded=0`); con la ciudad bloqueada a Bogotá es una
// RESTRICCIÓN (`bounded=1`): ver `parametrosDeBusqueda`.
const VIEWBOX_BOGOTA = "-74.35,4.95,-73.90,4.40";

/** Si el punto cae dentro de la caja de Bogotá y sus alrededores. */
export function dentroDeBogota(latitud: number, longitud: number): boolean {
  return latitud >= 4.4 && latitud <= 4.95 && longitud >= -74.35 && longitud <= -73.9;
}

export interface OpcionesConsulta {
  /** Lo que escribió el padre: de ahí se conserva el número si OSM no lo trae. */
  consulta?: string;
  /** La ciudad del formulario está bloqueada a Bogotá: no se ofrece nada fuera. */
  soloBogota?: boolean;
}

/** Los parámetros de Nominatim para una consulta ya normalizada. Pura: la usa el
 *  buscador y la prueba de la restricción. */
export function parametrosDeBusqueda(q: string, opciones: OpcionesConsulta = {}): URLSearchParams {
  const p = new URLSearchParams();
  p.set("format", "jsonv2");
  p.set("addressdetails", "1");
  p.set("limit", String(MAXIMO_RESULTADOS + 3));
  p.set("countrycodes", "co");
  p.set("accept-language", "es");
  p.set("viewbox", VIEWBOX_BOGOTA);
  if (opciones.soloBogota) p.set("bounded", "1");
  p.set("q", q);
  return p;
}

function sinTildes(t: string): string {
  return t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
}

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

// ---- Nomenclatura colombiana -------------------------------------------------

export interface Nomenclatura {
  /** "Carrera", "Calle", "Avenida Carrera", "Diagonal", "Transversal"... */
  via: string;
  /** Número de la vía con su letra: "91", "72A". */
  numeroVia: string;
  /** Número del cruce con su letra ("19A"), "" si solo escribió la vía. */
  cruce: string;
  /** Placa: "29", "" si solo escribió la vía. */
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
// tipo [carrera|calle si es avenida] número[letra] [bis] [sur|norte|este|oeste] [cruce[letra] [-] placa]
const PATRON_NOMENCLATURA = new RegExp(
  `^(${ALTERNATIVA_TIPOS})(?:\\s+(carrera|calle|cra|cl))?\\s*(\\d+)(?:\\s*([a-z])(?![a-z]))?(?:\\s+bis)?(?:\\s+(?:sur|norte|este|oeste))?` +
    `(?:\\s+(\\d+)(?:\\s*([a-z])(?![a-z]))?\\s*-?\\s*(\\d+))?\\s*$`,
);

/** Entiende "carrera 91 #19 A 29", "cra 91 19a-29", "kr 91 19-29", "cl 72 10 34",
 *  "dg", "tv", "av"... Devuelve null si no es nomenclatura reconocible. */
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

/** "#19A-29" a partir de lo que OSM llame número de casa ("19A-29", "19 A 29", "29"). */
export function formatearPlaca(crudo: string): string {
  const t = sinTildes(crudo).replace(/[#.]/g, " ").replace(/\s+/g, " ").trim().toUpperCase();
  const m = /^(\d+)\s*([A-Z])?\s*[-\s]\s*(\d+)$/.exec(t);
  if (m) return `#${m[1]}${m[2] ?? ""}-${m[3]}`;
  return t ? `#${t}` : "";
}

/** ¿La calle de OSM ("Carrera 91") es la misma vía que escribió el padre? */
function mismaVia(calleOsm: string, n: Nomenclatura): boolean {
  const osm = sinTildes(calleOsm).replace(/\s+/g, "");
  const propia = sinTildes(`${n.via}${n.numeroVia}`).replace(/\s+/g, "");
  return osm.startsWith(propia) && !/\d/.test(osm.charAt(propia.length));
}

export interface PartesDireccion {
  calle: string;
  /** house_number de OSM, si lo trae. */
  numeroOsm?: string;
  /** Lo que escribió el padre, para conservar su número. */
  consulta?: string;
  /** Lugares de menor a mayor: barrio, localidad, ciudad, código postal. */
  zona?: readonly string[];
}

export interface DireccionFormateada {
  /** "Carrera 91 #19A-29" */
  direccion: string;
  /** "Carrera 91 #19A-29, Barrio, Localidad, Bogotá" */
  completa: string;
  confirmarNumero: boolean;
  numeroDelPadre: boolean;
}

/** Arma la dirección legible. El número de OSM manda; si OSM solo resolvió la
 *  calle y el padre escribió número para ESA misma vía, se conserva el suyo y se
 *  marca para confirmar. Sin número de ninguno, también hay que confirmarlo. */
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

/** Lee la respuesta JSON de Nominatim: descarta lo malformado y lo que cae fuera
 *  de Colombia, y repite ninguna dirección. */
export function leerCandidatos(cuerpo: unknown, opciones: OpcionesConsulta = {}): Candidato[] {
  if (!Array.isArray(cuerpo)) return [];
  const vistos = new Set<string>();
  // Con su puntaje: en Bogotá primero, y con número de casa antes que la calle
  // a secas. A igual puntaje manda el orden de relevancia que trae Nominatim.
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
    // Un sitio (colegio, centro comercial) se muestra por su nombre, pero lo que
    // se guarda es su dirección: el repartidor busca una calle, no un letrero.
    const esSitio = !!nombre && nombre !== calle && item["category"] !== "highway";
    const direccion = f.direccion || nombre || texto(item["display_name"]).split(",")[0]?.trim() || "";
    if (!direccion) continue;
    const secundario = zona.filter((parte, i, todas) => todas.indexOf(parte) === i).filter((p) => p !== texto(a["postcode"])).join(", ");
    const completa = f.completa || [direccion, ...zona].join(", ");

    // `osm_id` llega como número: `texto` solo acepta cadenas.
    const id = `${texto(item["osm_type"])}${String(item["osm_id"] ?? "")}`;
    if (opciones.soloBogota && !dentroDeBogota(latitud, longitud)) continue;
    // La misma calle del mismo barrio es UNA opción aunque OSM la parta en
    // tramos con coordenadas distintas ("Carrera 91" cinco veces). Con número
    // de casa la dirección ya es distinta y se conserva.
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
      puntaje: (dentroDeBogota(latitud, longitud) ? 2 : 0) + (numero ? 1 : 0),
    });
  }
  // `sort` es estable: el empate conserva el orden de relevancia de OSM.
  return salida
    .sort((a, b) => b.puntaje - a.puntaje)
    .slice(0, MAXIMO_RESULTADOS)
    .map((x) => x.candidato);
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

  async buscar(consulta: string, opciones: OpcionesConsulta = {}): Promise<Candidato[]> {
    const original = consulta;
    const q = normalizarConsulta(consulta);
    if (q.length < MINIMO_CARACTERES) {
      throw new ErrorBusqueda(400, "consulta_corta", `Escribe al menos ${MINIMO_CARACTERES} letras de la dirección.`);
    }
    // La restricción cambia la respuesta: no comparte caché con la búsqueda libre.
    const clave = `${opciones.soloBogota ? "bogota|" : ""}${q.toLowerCase()}`;

    const guardado = this.cache.get(clave);
    if (guardado && guardado.vence > this.ahora()) return guardado.candidatos;
    // Dos visitantes buscando lo mismo a la vez comparten una sola petición.
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

  private async consultar(q: string, clave: string, opciones: OpcionesConsulta): Promise<Candidato[]> {
    const intervalo = this.op.intervaloMs ?? INTERVALO_MS;
    const espera = this.ultimaPeticion + intervalo - this.ahora();
    if (espera > 0) await (this.op.esperar ?? ((ms) => new Promise<void>((r) => setTimeout(r, ms))))(espera);
    this.ultimaPeticion = this.ahora();

    const url = new URL(this.op.url ?? "https://nominatim.openstreetmap.org/search");
    url.search = parametrosDeBusqueda(q, opciones).toString();

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

    const candidatos = leerCandidatos(cuerpo, opciones);
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
