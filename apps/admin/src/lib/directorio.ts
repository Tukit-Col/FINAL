// Los logos del directorio de Bogota para las paginas de servidor del admin.
// El JSON es la copia unica de `@tukit/contrato`; se indexa una vez por proceso
// y se le pasa a la regla pura `logoDeColegio` (Identidad primero, luego esto).
// Solo lo importan Server Components: el navegador lo pide a
// `/directorio-colegios.json` cuando lo necesita.

import directorio from "@tukit/contrato/directorio-colegios.json";
import { imagenesPorDane, type EntradaDirectorio } from "@tukit/contrato";

let imagenes: Map<string, string> | null = null;

export function imagenesDelDirectorio(): ReadonlyMap<string, string> {
  imagenes ??= imagenesPorDane(directorio as EntradaDirectorio[]);
  return imagenes;
}
