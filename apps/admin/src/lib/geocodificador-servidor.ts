// El geocodificador conectado a la red y al disco. Solo en el servidor: el
// navegador nunca habla con Nominatim (la IP y el volumen son del servidor, y
// asi el cache y el limite de una peticion por segundo valen para todos).
//
// El cache vive en un JSON dentro de `apps/admin/.cache/` (fuera de git).
// `TUKIT_GEOCACHE_DIR` lo mueve; `TUKIT_NOMINATIM_CONTACTO` es obligatorio: la
// politica de Nominatim pide identificar la app con un contacto real, y sin
// contacto no se consulta.
import "server-only";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { Geocodificador, type AlmacenCache, type EntradaCache } from "./geocodificador";

function directorio(): string {
  return process.env["TUKIT_GEOCACHE_DIR"] ?? join(process.cwd(), ".cache");
}

const almacenEnDisco: AlmacenCache = {
  async leer() {
    try {
      return JSON.parse(await readFile(join(directorio(), "geocodificacion.json"), "utf8")) as Record<
        string,
        EntradaCache
      >;
    } catch {
      return {};
    }
  },
  async escribir(datos) {
    await mkdir(directorio(), { recursive: true });
    const destino = join(directorio(), "geocodificacion.json");
    // Escritura atomica: un crash a mitad no deja un JSON truncado.
    const temporal = `${destino}.${process.pid}.tmp`;
    await writeFile(temporal, JSON.stringify(datos), "utf8");
    await rename(temporal, destino);
  },
};

let instancia: Geocodificador | null = null;

/** El geocodificador del proceso, o `null` si falta el contacto (entonces el
 *  mapa lista las direcciones sin marcador y avisa por que). */
export function geocodificadorDelServidor(): Geocodificador | null {
  const contacto = process.env["TUKIT_NOMINATIM_CONTACTO"]?.trim();
  if (!contacto) return null;
  instancia ??= new Geocodificador({ contacto, fetchFn: fetch, almacen: almacenEnDisco });
  return instancia;
}
