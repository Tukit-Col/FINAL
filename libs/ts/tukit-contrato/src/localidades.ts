// Las 20 localidades de Bogotá y cómo sacarlas de una dirección de OpenStreetMap.
//
// Decisiones:
// - La localidad se guarda con su nombre visible canónico (el de esta lista) y no con lo que escriba el
//   mapa, que puede decir "Localidad de Chapinero" o "Santafé": la logística agrupa por localidad.
// - No hay polígonos: si los componentes no traen una localidad reconocible, la elige el acudiente.
// - Es puro y autocontenido, para que lo usen el checkout (web) y el admin y corra con `node --test`.

export const LOCALIDADES_BOGOTA = [
  "Usaquén",
  "Chapinero",
  "Santa Fe",
  "San Cristóbal",
  "Usme",
  "Tunjuelito",
  "Bosa",
  "Kennedy",
  "Fontibón",
  "Engativá",
  "Suba",
  "Barrios Unidos",
  "Teusaquillo",
  "Los Mártires",
  "Antonio Nariño",
  "Puente Aranda",
  "La Candelaria",
  "Rafael Uribe Uribe",
  "Ciudad Bolívar",
  "Sumapaz",
] as const;

export type LocalidadBogota = (typeof LOCALIDADES_BOGOTA)[number];

function clave(texto: string): string {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .replace(/^localidad\s+(de\s+)?/, "")
    .replace(/^(la|los|las|el)\s+/, "")
    .replace(/[^a-z0-9]/g, "");
}

const POR_CLAVE = new Map<string, LocalidadBogota>([
  ...LOCALIDADES_BOGOTA.map((l) => [clave(l), l] as const),
  [clave("Rafael Uribe"), "Rafael Uribe Uribe"],
]);

export function localidadCanonica(texto: string | null | undefined): LocalidadBogota | null {
  if (!texto) return null;
  return POR_CLAVE.get(clave(texto)) ?? null;
}

const CLAVES_BOGOTA = new Set(["bogota", "bogotadc", "santafedebogota", "santafedebogotadc"]);

export function esBogota(ciudad: string | null | undefined): boolean {
  return !!ciudad && CLAVES_BOGOTA.has(clave(ciudad));
}

export interface DireccionDerivada {
  ciudad: string;
  localidad: LocalidadBogota | "";
  departamento: string;
}

export function enlaceGoogleMaps(envio: {
  direccion: string;
  ciudad?: string | null;
  latitud?: number | null;
  longitud?: number | null;
}): string {
  const { latitud, longitud } = envio;
  if (typeof latitud === "number" && typeof longitud === "number") {
    return `https://www.google.com/maps/search/?api=1&query=${latitud},${longitud}`;
  }
  const direccion = envio.direccion.trim();
  const ciudad = envio.ciudad?.trim() ?? "";
  const consulta = ciudad && !clave(direccion).includes(clave(ciudad)) ? `${direccion}, ${ciudad}` : direccion;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(consulta)}`;
}

const CAMPOS_LOCALIDAD_OSM = ["suburb", "city_district", "borough", "quarter"] as const;
const CAMPOS_CIUDAD_OSM = ["city", "town", "village", "municipality"] as const;

export function direccionDesdeNominatim(
  direccion: Readonly<Record<string, string | undefined>> | null | undefined,
): DireccionDerivada {
  const a = direccion ?? {};
  const estado = a["state"]?.trim() ?? "";
  const ciudadOsm = CAMPOS_CIUDAD_OSM.map((campo) => a[campo]?.trim() ?? "").find(Boolean) ?? "";
  const enBogota = /^bogot[aá]/i.test(estado) || /^bogot[aá]/i.test(ciudadOsm);

  const ciudad = enBogota ? "Bogotá" : ciudadOsm;
  const departamento = enBogota ? "Bogotá, D.C." : estado;

  let localidad: LocalidadBogota | "" = "";
  if (enBogota) {
    for (const campo of CAMPOS_LOCALIDAD_OSM) {
      const casada = localidadCanonica(a[campo]);
      if (casada) {
        localidad = casada;
        break;
      }
    }
  }
  return { ciudad, localidad, departamento };
}
