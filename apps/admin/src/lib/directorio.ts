import directorio from "@tukit/contrato/directorio-colegios.json";
import { imagenesPorDane, type EntradaDirectorio } from "@tukit/contrato";

let imagenes: Map<string, string> | null = null;

export function imagenesDelDirectorio(): ReadonlyMap<string, string> {
  imagenes ??= imagenesPorDane(directorio as EntradaDirectorio[]);
  return imagenes;
}
