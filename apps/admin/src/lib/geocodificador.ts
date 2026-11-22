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
  localidad?: string | null;
}

export type ResultadoGeo = Punto | null | "pendiente";

export interface OpcionesGeocodificador {
  contacto: string;
  fetchFn: typeof fetch;
  almacen: AlmacenCache;
  esperar?: (ms: number) => Promise<void>;
  ahora?: () => number;
  maxNuevas?: number;
  intervaloMs?: number;
  url?: string;
}

export const INTERVALO_MS = 1100;
export const TTL_FALLO_MS = 7 * 24 * 3_600_000;
export const ATRIBUCION = "© OpenStreetMap contributors";

const CAJA_COLOMBIA = { sur: -4.3, norte: 13.6, oeste: -81.8, este: -66.8 };

export function dentroDeColombia(p: Punto): boolean {
  return (
    p.lat >= CAJA_COLOMBIA.sur &&
    p.lat <= CAJA_COLOMBIA.norte &&
    p.lon >= CAJA_COLOMBIA.oeste &&
    p.lon <= CAJA_COLOMBIA.este
  );
}

export function claveDireccion(d: DireccionAGeocodificar): string {
  const limpio = (t: string | null) =>
    (t ?? "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  const base = [limpio(d.direccion), limpio(d.ciudad), limpio(d.departamento)];
  return (d.localidad ? [...base, limpio(d.localidad)] : base).join("|");
}

export function agenteUsuario(contacto: string): string {
  return `TukitAdmin/0.1 (logistica; contacto: ${contacto})`;
}

export function leerRespuestaNominatim(cuerpo: unknown): Punto | null {
  if (!Array.isArray(cuerpo) || cuerpo.length === 0) return null;
  const primero = cuerpo[0] as { lat?: unknown; lon?: unknown; addresstype?: unknown };
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

export function normalizarDireccion(direccion: string): string {
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
  private cola: Promise<unknown> = Promise.resolve();

  private readonly op: OpcionesGeocodificador;

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
