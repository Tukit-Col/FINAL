// Geocodificacion de direcciones con Nominatim (OpenStreetMap), SOLO en el servidor.
//
// Cumple la politica de uso de Nominatim (operations.osmfoundation.org/policies/nominatim):
//   - maximo una peticion por segundo, sin importar cuantas paginas la pidan a la vez;
//   - User-Agent que identifica la app y trae un contacto real (sin contacto no se consulta);
//   - nada de geocodificacion masiva: cada direccion se consulta UNA vez y se guarda,
//     tambien cuando no aparece (cache negativa, con reintento tras `TTL_FALLO_MS`);
//   - trabajo acotado por llamada (`maxNuevas`): lo que sobre queda "pendiente" y se
//     resuelve en la siguiente visita, en vez de dejar la pagina colgada.
//
// Este modulo no toca disco ni red por su cuenta: recibe `fetch`, el almacen y el
// reloj. `geocodificador-servidor.ts` los conecta; las pruebas usan dobles.

export interface Punto {
  lat: number;
  lon: number;
}

export interface EntradaCache {
  lat: number | null;
  lon: number | null;
  consultado_en: string;
}

export interface AlmacenCache {
  leer(): Promise<Record<string, EntradaCache>>;
  escribir(datos: Record<string, EntradaCache>): Promise<void>;
}

export interface DireccionAGeocodificar {
  direccion: string;
  ciudad: string;
  departamento: string | null;
  /** Localidad de Bogota (Fontibon, Kennedy...): acota el respaldo por via. */
  localidad?: string | null;
}

/** Resultado por direccion: un punto, `null` si Nominatim no la encontro, o
 *  `"pendiente"` si no hubo cupo en esta llamada. */
export type ResultadoGeo = Punto | null | "pendiente";

export interface OpcionesGeocodificador {
  /** Correo o URL de contacto que va en el User-Agent. Requerido por la politica. */
  contacto: string;
  fetchFn: typeof fetch;
  almacen: AlmacenCache;
  esperar?: (ms: number) => Promise<void>;
  ahora?: () => number;
  /** Cuantas direcciones NUEVAS se consultan por llamada. */
  maxNuevas?: number;
  intervaloMs?: number;
  url?: string;
}

export const INTERVALO_MS = 1100;
export const TTL_FALLO_MS = 7 * 24 * 3_600_000;
export const ATRIBUCION = "© OpenStreetMap contributors";

// Colombia continental e insular: una respuesta fuera de aqui es un homonimo de
// otro pais (una "Calle 1" en Madrid) y no se pinta.
const CAJA_COLOMBIA = { sur: -4.3, norte: 13.6, oeste: -81.8, este: -66.8 };

export function dentroDeColombia(p: Punto): boolean {
  return (
    p.lat >= CAJA_COLOMBIA.sur &&
    p.lat <= CAJA_COLOMBIA.norte &&
    p.lon >= CAJA_COLOMBIA.oeste &&
    p.lon <= CAJA_COLOMBIA.este
  );
}

/** La clave de cache de una direccion: sin tildes, en minusculas y con los
 *  espacios colapsados, para que "Cra 7 # 8-9 " y "cra 7 # 8-9" sean la misma. */
export function claveDireccion(d: DireccionAGeocodificar): string {
  const limpio = (t: string | null) =>
    (t ?? "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  // La localidad entra solo si viene: las claves viejas (sin ella) siguen sirviendo.
  const base = [limpio(d.direccion), limpio(d.ciudad), limpio(d.departamento)];
  return (d.localidad ? [...base, limpio(d.localidad)] : base).join("|");
}

/** El User-Agent que exige la politica: nombre de la app y como contactarnos. */
export function agenteUsuario(contacto: string): string {
  return `TukitAdmin/0.1 (logistica; contacto: ${contacto})`;
}

/** Lee la primera coincidencia de la respuesta JSON de Nominatim, validada. */
export function leerRespuestaNominatim(cuerpo: unknown): Punto | null {
  if (!Array.isArray(cuerpo) || cuerpo.length === 0) return null;
  const primero = cuerpo[0] as { lat?: unknown; lon?: unknown; addresstype?: unknown };
  // "Bogota ciudad" o la localidad entera no son la direccion: pintarlas en el mapa
  // pone el pin en un sitio que parece exacto y no lo es.
  if (typeof primero.addresstype === "string" && AREAS.has(primero.addresstype)) return null;
  const lat = Number(primero.lat);
  const lon = Number(primero.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const punto = { lat, lon };
  return dentroDeColombia(punto) ? punto : null;
}

const AREAS = new Set(["city", "town", "state", "county", "municipality", "country", "region", "city_district", "borough"]);

const VIAS: [RegExp, string][] = [
  [/^(KR|KRA|CRA|CR|CARRERA)\.?\s+/i, "Carrera "],
  [/^(CL|CLL|CALLE)\.?\s+/i, "Calle "],
  [/^(AK|AV\.?\s*KR|AVENIDA CARRERA)\.?\s+/i, "Avenida Carrera "],
  [/^(AC|AV\.?\s*CL|AVENIDA CALLE)\.?\s+/i, "Avenida Calle "],
  [/^(DG|DIAG|DIAGONAL)\.?\s+/i, "Diagonal "],
  [/^(TV|TR|TRANSV|TRANSVERSAL)\.?\s+/i, "Transversal "],
];

/** "KR 109 # 23 D - 35" (formato del DANE) -> "Carrera 109 23D-35": como lo escribe OSM. */
export function normalizarDireccion(direccion: string): string {
  // El DANE junta varias sedes con "--" ("KR 99 # 17 A - 62 -- 20 -- 80 -- KR 98 ..."):
  // el punto del colegio es la primera direccion.
  let t = direccion.split(/\s+--\s+/)[0]!.trim().replace(/\s+/g, " ");
  for (const [re, nombre] of VIAS) {
    if (re.test(t)) {
      t = t.replace(re, nombre);
      break;
    }
  }
  return t
    .replace(/\s*(#|No\.?|N°)\s*/i, " ")
    .replace(/(\d+)\s+([A-Z])\b/g, "$1$2")
    .replace(/\s*-\s*/g, "-")
    .replace(/\s+BIS\b/gi, " Bis");
}

/** Solo la via ("Carrera 109"): el respaldo cuando OSM no tiene la placa. */
function soloVia(direccion: string): string | null {
  const m = normalizarDireccion(direccion).match(/^((?:Avenida )?(?:Carrera|Calle|Diagonal|Transversal) \d+[A-Z]?(?: Bis)?)/);
  return m ? m[1]! : null;
}

function consulta(d: DireccionAGeocodificar): string {
  return [normalizarDireccion(d.direccion), d.localidad, d.ciudad, d.departamento, "Colombia"].filter(Boolean).join(", ");
}

function consultaDeVia(d: DireccionAGeocodificar): string | null {
  const via = soloVia(d.direccion);
  return via ? [via, d.localidad, d.ciudad, "Colombia"].filter(Boolean).join(", ") : null;
}

export class Geocodificador {
  private ultimaPeticion = 0;
  // Cola de una sola fila: dos paginas a la vez no se saltan el intervalo ni se
  // pisan al escribir la cache.
  private cola: Promise<unknown> = Promise.resolve();

  private readonly op: OpcionesGeocodificador;

  // Campo explicito y no `private readonly` en el parametro: `node --test` solo
  // quita tipos, no ejecuta esa sintaxis.
  constructor(op: OpcionesGeocodificador) {
    this.op = op;
  }

  resolver(direcciones: readonly DireccionAGeocodificar[]): Promise<Map<string, ResultadoGeo>> {
    const turno = this.cola.then(() => this.resolverEnTurno(direcciones));
    this.cola = turno.catch(() => undefined);
    return turno;
  }

  private async resolverEnTurno(
    direcciones: readonly DireccionAGeocodificar[],
  ): Promise<Map<string, ResultadoGeo>> {
    const ahora = this.op.ahora ?? Date.now;
    const maxNuevas = this.op.maxNuevas ?? 6;
    const cache = await this.op.almacen.leer();
    const salida = new Map<string, ResultadoGeo>();
    const porConsultar = new Map<string, DireccionAGeocodificar>();

    for (const d of direcciones) {
      const clave = claveDireccion(d);
      if (salida.has(clave) || porConsultar.has(clave)) continue;
      const guardada = cache[clave];
      if (guardada) {
        if (guardada.lat !== null && guardada.lon !== null) {
          salida.set(clave, { lat: guardada.lat, lon: guardada.lon });
          continue;
        }
        const edad = ahora() - new Date(guardada.consultado_en).getTime();
        if (edad < TTL_FALLO_MS) {
          salida.set(clave, null);
          continue;
        }
      }
      porConsultar.set(clave, d);
    }

    let consultadas = 0;
    let sucio = false;
    for (const [clave, d] of porConsultar) {
      if (consultadas >= maxNuevas) {
        salida.set(clave, "pendiente");
        continue;
      }
      consultadas += 1;
      let punto: Punto | null;
      try {
        punto = await this.consultarNominatim(d);
      } catch {
        // Red caida o 429/5xx: no se guarda nada (no es "no existe") y se reintenta luego.
        salida.set(clave, "pendiente");
        continue;
      }
      cache[clave] = {
        lat: punto?.lat ?? null,
        lon: punto?.lon ?? null,
        consultado_en: new Date(ahora()).toISOString(),
      };
      sucio = true;
      salida.set(clave, punto);
    }
    if (sucio) await this.op.almacen.escribir(cache);
    return salida;
  }

  private async consultarNominatim(d: DireccionAGeocodificar): Promise<Punto | null> {
    const exacta = await this.pedirNominatim(consulta(d));
    if (exacta) return exacta;
    const via = consultaDeVia(d);
    return via ? this.pedirNominatim(via) : null;
  }

  private async pedirNominatim(q: string): Promise<Punto | null> {
    const esperar = this.op.esperar ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
    const ahora = this.op.ahora ?? Date.now;
    const intervalo = this.op.intervaloMs ?? INTERVALO_MS;
    const falta = this.ultimaPeticion + intervalo - ahora();
    if (falta > 0) await esperar(falta);
    this.ultimaPeticion = ahora();

    const url = new URL(this.op.url ?? "https://nominatim.openstreetmap.org/search");
    url.searchParams.set("q", q);
    url.searchParams.set("format", "jsonv2");
    url.searchParams.set("limit", "1");
    url.searchParams.set("countrycodes", "co");
    const respuesta = await this.op.fetchFn(url, {
      headers: { "User-Agent": agenteUsuario(this.op.contacto), "Accept-Language": "es" },
    });
    if (!respuesta.ok) throw new Error(`nominatim ${respuesta.status}`);
    return leerRespuestaNominatim(await respuesta.json());
  }
}
