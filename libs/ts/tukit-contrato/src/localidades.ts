// Las 20 localidades de Bogota y como sacarlas de una direccion de Google
// Places (New). Puro y autocontenido: lo usan el checkout (web) para llenar
// ciudad/localidad/departamento al elegir una sugerencia y el admin para el
// enlace a Google Maps del pedido, y corre con `node --test`.
//
// La localidad se guarda con su nombre visible canonico (el de esta lista), no
// con lo que Google escriba: Google dice "Localidad de Chapinero", "Santafé" o
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

// Un componente de direccion de Places (New): `place.addressComponents`.
export interface ComponenteDireccion {
  longText: string | null;
  shortText: string | null;
  types: readonly string[];
}

export interface DireccionDerivada {
  ciudad: string;
  localidad: LocalidadBogota | "";
  departamento: string;
}

// En que componentes buscar la localidad, en orden. Google la pone en
// cualquiera de estos segun el barrio. `neighborhood` no: es el barrio, y hay
// barrios que se llaman como otra localidad (el barrio Santa Fe queda en Los
// Mártires). Sin localidad reconocible, la elige el acudiente.
const TIPOS_LOCALIDAD = [
  "sublocality_level_1",
  "sublocality",
  "administrative_area_level_3",
  "administrative_area_level_2",
];

// De los componentes de una direccion a lo que el checkout pre-llena. La
// localidad queda vacia fuera de Bogota o si ningun componente es una de las 20
// (entonces la elige el acudiente).
export function direccionDesdeComponentes(
  componentes: readonly ComponenteDireccion[] | null | undefined,
): DireccionDerivada {
  const lista = componentes ?? [];
  const de = (tipo: string) =>
    lista.filter((c) => c.types.includes(tipo)).map((c) => c.longText?.trim() || c.shortText?.trim() || "");
  const primero = (tipo: string) => de(tipo).find(Boolean) ?? "";

  const departamento = primero("administrative_area_level_1");
  const ciudad =
    primero("locality") ||
    primero("administrative_area_level_2") ||
    // Bogota es distrito capital: a veces solo llega como departamento.
    (esBogota(departamento) ? departamento : "");

  let localidad: LocalidadBogota | "" = "";
  if (esBogota(ciudad)) {
    for (const tipo of TIPOS_LOCALIDAD) {
      const casada = lista
        .filter((c) => c.types.includes(tipo))
        .flatMap((c) => [c.longText, c.shortText])
        .map(localidadCanonica)
        .find(Boolean);
      if (casada) {
        localidad = casada;
        break;
      }
    }
  }
  return { ciudad, localidad, departamento };
}

// El enlace "Ver en Google Maps" de un envio. Sin coordenadas: busca por el
// texto de la direccion (con la ciudad si no la trae) y, si el checkout guardo
// el `place_id`, lo fija para que Maps abra ese lugar exacto.
export function enlaceGoogleMaps(envio: {
  direccion: string;
  ciudad?: string | null;
  google_place_id?: string | null;
}): string {
  const direccion = envio.direccion.trim();
  const ciudad = envio.ciudad?.trim() ?? "";
  const consulta = ciudad && !clave(direccion).includes(clave(ciudad)) ? `${direccion}, ${ciudad}` : direccion;
  let url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(consulta)}`;
  const lugar = envio.google_place_id?.trim();
  if (lugar) url += `&query_place_id=${encodeURIComponent(lugar)}`;
  return url;
}
