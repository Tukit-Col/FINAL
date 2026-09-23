// `/colegios` — P4, la BD durable de colegios y listas.
//
// La superficie de gestión: todos los colegios con su logo, si ya son aliados
// (tienen al menos un grado revisado) y sus grados verificados con enlace a
// cada lista. Aliados primero, después los que aún no tienen ninguna lista.
//
// Server Component: `colegios()` sale del origen directamente.

import { origenDeDatos } from "@tukit/contrato/servidor";
import TarjetaColegio from "@/components/TarjetaColegio";
import styles from "./Colegios.module.css";

export const dynamic = "force-dynamic";

export default async function PaginaColegios() {
  const colegios = await origenDeDatos().colegios();

  const esAliado = (c: (typeof colegios)[number]) =>
    (c.es_partner ?? c.grados.length > 0) ? 0 : 1;
  // Aliados arriba; dentro de cada grupo, alfabético por nombre.
  const ordenados = [...colegios].sort(
    (a, b) => esAliado(a) - esAliado(b) || a.nombre.localeCompare(b.nombre, "es"),
  );

  const aliados = ordenados.filter((c) => (c.es_partner ?? c.grados.length > 0));

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Colegios y listas</h1>
          <p className={styles.bajada}>
            La base durable de colegios. Un colegio se vuelve aliado en cuanto tiene su primer
            grado revisado; hasta entonces no aparece en el selector del acudiente.
          </p>
        </div>
        <dl className={styles.resumen}>
          <div>
            <dt>Aliados</dt>
            <dd className="cifra">{aliados.length}</dd>
          </div>
          <div>
            <dt>Colegios en total</dt>
            <dd className="cifra">{colegios.length}</dd>
          </div>
        </dl>
      </header>

      {colegios.length === 0 ? (
        <p className={styles.vacio}>Todavía no hay colegios cargados.</p>
      ) : (
        <div className={styles.rejilla}>
          {ordenados.map((colegio) => (
            <TarjetaColegio key={colegio.colegio_id} colegio={colegio} />
          ))}
        </div>
      )}
    </div>
  );
}
