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
    const temporal = `${destino}.${process.pid}.tmp`;
    await writeFile(temporal, JSON.stringify(datos), "utf8");
    await rename(temporal, destino);
  },
};

let instancia: Geocodificador | null = null;

export function geocodificadorDelServidor(): Geocodificador | null {
  const contacto = process.env["TUKIT_NOMINATIM_CONTACTO"]?.trim();
  if (!contacto) return null;
  instancia ??= new Geocodificador({ contacto, fetchFn: fetch, almacen: almacenEnDisco });
  return instancia;
}
