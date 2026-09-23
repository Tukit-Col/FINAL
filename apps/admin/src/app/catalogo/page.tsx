// `/catalogo` — el gestor de huecos de catálogo (CABLEADO).
//
// Lista los conceptos que el catálogo NO cubre bien, con datos reales de
// `catalogo()`: los que no tienen ningún producto (hueco duro) y los que tienen
// productos pero no los tres niveles (cobertura parcial). Para cada uno se puede
// dar de alta un producto con `altaProducto()` — la misma mutación que usa AD-07
// en la revisión, aquí sin línea de por medio (el contrato lo admite: sin
// trabajo/item solo agrega al catálogo).
//
// Server Component: lee el origen directo. El alta vive en un componente de
// cliente porque escribe.

import { PackageSearch } from "lucide-react";
import type { ConceptoCatalogo } from "@tukit/contrato";
import { coberturaDe } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import GestorHuecos from "@/components/GestorHuecos";
import styles from "./Catalogo.module.css";

export const dynamic = "force-dynamic";

export default async function PaginaCatalogo() {
  const catalogo = await origenDeDatos().catalogo();

  // Los huecos primero (sin ningún producto), después la cobertura parcial.
  // Dentro de cada grupo, lo más pedido arriba: es lo que más duele que falte.
  const clasificar = (c: ConceptoCatalogo) => coberturaDe(c);
  const conceptos = [...catalogo.conceptos].sort(
    (a, b) => b.frecuencia_demanda - a.frecuencia_demanda,
  );
  const huecos = conceptos.filter((c) => clasificar(c) === "sin_productos");
  const parciales = conceptos.filter((c) => clasificar(c) === "parcial");

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Catálogo · huecos</h1>
          <p className={styles.bajada}>
            Lo que el catálogo todavía no cubre. Un hueco es lo que el acudiente ve como
            &ldquo;esto no lo tenemos&rdquo;: darlo de alta aquí lo cierra para todos los
            trabajos, no solo para uno.
          </p>
        </div>
        <dl className={styles.resumen}>
          <div>
            <dt>Sin ningún producto</dt>
            <dd className="cifra">{catalogo.resumen.conceptos_sin_producto}</dd>
          </div>
          <div>
            <dt>Con los tres niveles</dt>
            <dd className="cifra">{catalogo.resumen.conceptos_con_tres_niveles}</dd>
          </div>
          <div>
            <dt>Conceptos en total</dt>
            <dd className="cifra">{catalogo.resumen.conceptos}</dd>
          </div>
        </dl>
      </header>

      {huecos.length === 0 && parciales.length === 0 ? (
        <div className={styles.vacio}>
          <PackageSearch size={22} aria-hidden="true" />
          <p>No hay huecos: todos los conceptos tienen al menos un producto.</p>
        </div>
      ) : (
        <GestorHuecos
          huecos={huecos.map((c) => ({
            codigo: c.codigo,
            nombre: c.nombre_canonico,
            categoria: c.categoria,
            demanda: c.frecuencia_demanda,
            productos: 0,
          }))}
          parciales={parciales.map((c) => ({
            codigo: c.codigo,
            nombre: c.nombre_canonico,
            categoria: c.categoria,
            demanda: c.frecuencia_demanda,
            productos: c.productos.length,
          }))}
        />
      )}
    </div>
  );
}
