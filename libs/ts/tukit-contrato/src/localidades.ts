// Las 20 localidades de Bogota y como sacarlas de una direccion de
// OpenStreetMap. Puro y autocontenido: lo usan el checkout (web) para llenar
// ciudad/localidad/departamento al elegir una sugerencia y el admin para el
// enlace a Google Maps del pedido, y corre con `node --test`.
//
// La localidad se guarda con su nombre visible canonico (el de esta lista), no
// con lo que escriba el mapa: puede decir "Localidad de Chapinero", "Santafé" o
// "Los Mártires" segun la direccion, y la logistica agrupa por localidad. No hay
// poligonos: si los componentes no traen una localidad reconocible, el
// acudiente la elige de la lista.

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

// La clave de comparacion: sin acentos, mayusculas, espacios ni signos, sin el
// prefijo "Localidad de" y sin el articulo inicial ("Los Mártires" y "Mártires"
// son la misma).
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
  // Como la escriben a veces, sin el segundo apellido.
  [clave("Rafael Uribe"), "Rafael Uribe Uribe"],
]);

// La localidad canonica de un texto, o `null` si no es una de las 20.
export function localidadCanonica(texto: string | null | undefined): LocalidadBogota | null {
  if (!texto) return null;
  return POR_CLAVE.get(clave(texto)) ?? null;
}

const CLAVES_BOGOTA = new Set(["bogota", "bogotadc", "santafedebogota", "santafedebogotadc"]);

// Si una ciudad es Bogota ("Bogotá", "Bogotá, D.C.", "bogota"...): la
// localidad solo aplica ahi.
export function esBogota(ciudad: string | null | undefined): boolean {
  return !!ciudad && CLAVES_BOGOTA.has(clave(ciudad));
}

export interface DireccionDerivada {
  ciudad: string;
  localidad: LocalidadBogota | "";
  departamento: string;
}

// El enlace "Ver en Google Maps" de un envio. Con coordenadas (la direccion se
// confirmo en el mapa de OpenStreetMap, ADR 0049) abre ese punto exacto. Sin
// ellas busca por el texto de la direccion (con la ciudad si no la trae).
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

// La direccion de una respuesta de Nominatim (OpenStreetMap, `addressdetails=1`)
// a lo que el checkout pre-llena. En Bogota
// escribe la ciudad como "Bogotá ciudad", el departamento como "Bogotá,
// Distrito Capital" y la localidad en `suburb` como "Localidad Chapinero".
// `localidadCanonica` ya ignora el prefijo "Localidad", asi que basta probar los
// campos donde OSM la suele poner. `neighbourhood` no: es el barrio, y hay barrios que se llaman como otra localidad.
// Sin localidad reconocible la elige el acudiente.
const CAMPOS_LOCALIDAD_OSM = ["suburb", "city_district", "borough", "quarter"] as const;
const CAMPOS_CIUDAD_OSM = ["city", "town", "village", "municipality"] as const;

export function direccionDesdeNominatim(
  direccion: Readonly<Record<string, string | undefined>> | null | undefined,
): DireccionDerivada {
  const a = direccion ?? {};
  const estado = a["state"]?.trim() ?? "";
  const ciudadOsm = CAMPOS_CIUDAD_OSM.map((campo) => a[campo]?.trim() ?? "").find(Boolean) ?? "";
  // Sin `\b`: en JavaScript la "á" no cuenta como letra y el borde de palabra
  // nunca casaria tras "Bogotá".
  const enBogota = /^bogot[aá]/i.test(estado) || /^bogot[aá]/i.test(ciudadOsm);

  // Bogota es distrito capital: la ciudad y el departamento se normalizan a los
  // nombres que ya usa el resto del sistema (`esBogota` los reconoce).
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
