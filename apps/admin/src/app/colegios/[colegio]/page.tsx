// `/colegios/{colegio}` — P4, el perfil de un colegio, EDITABLE (P1b).
//
// Muestra la ficha del colegio (logo, contactos de la secretaría académica,
// sitio, dirección) y sus grados verificados. La lectura sale de
// `colegio(colegioId)` (`GET /v1/colegios/{id}`, forma `ColegioDetalle`); la
// EDICIÓN vive en el formulario cliente `PerfilColegio`, que manda un PATCH por
// el Route Handler `/api/colegios/{id}` y re-pinta con lo que el backend
// devuelve. Los contactos son del colegio, nunca de un menor (§12.4).
//
// Server Component: `colegio()` sale del origen directamente. Un 404
// (`colegio_no_existe`) se traduce a `notFound()`.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { ColegioDetalle } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import PerfilColegio from "@/components/PerfilColegio";
import styles from "../Colegios.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ colegio: string }>;
}

export default async function PaginaColegio({ params }: Props) {
  const { colegio: colegioId } = await params;

  let colegio: ColegioDetalle;
  try {
    colegio = await origenDeDatos().colegio(colegioId);
  } catch (causa) {
    if (causa instanceof ErrorTukit && causa.estado === 404) notFound();
    throw causa;
  }

  // Los grados verificados no vienen en el detalle; se derivan del selector
  // (`colegios()`), la única superficie que los publica.
  const colegios = await origenDeDatos().colegios();
  const resumen = colegios.find((c) => c.colegio_id === colegioId);
  const grados = resumen?.grados ?? [];
  const esAliado = resumen?.es_partner ?? grados.length > 0;

  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href="/colegios">← Colegios y listas</Link>
      </nav>

      <header className={styles.encabezado}>
        <div className={styles.perfilIdentidad}>
          {colegio.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className={styles.logoGrande} src={colegio.logo_url} alt="" />
          ) : (
            <span className={styles.logoVacioGrande} aria-hidden="true">
              {colegio.nombre.slice(0, 1)}
            </span>
          )}
          <div>
            <h1>{colegio.nombre}</h1>
            <span className={esAliado ? styles.insigniaAliado : styles.insigniaBorrador}>
              {esAliado ? "Aliado" : "Sin listas revisadas"}
            </span>
          </div>
        </div>
      </header>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Ficha del colegio</h2>
        <p className={styles.bajada}>
          Datos de identidad y marca del colegio. Los contactos son de la secretaría académica —
          nunca de un menor. Guardar manda solo lo que cambió.
        </p>
        <PerfilColegio colegio={colegio} />
      </section>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Grados verificados</h2>
        {grados.length === 0 ? (
          <p className={styles.sinGrados}>
            Ningún grado revisado. <Link href="/onboarding">Sube una lista</Link>.
          </p>
        ) : (
          <ul className={styles.listaGrados}>
            {grados.map((grado) => (
              <li key={grado}>
                <Link
                  href={`/colegios/${encodeURIComponent(colegio.colegio_id)}/${encodeURIComponent(grado)}`}
                >
                  {grado}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
