// Tarjeta de un colegio en la BD de colegios y listas (P4). Muestra el logo del
// aliado (si cargó marca), su nombre, si ya es aliado (tiene al menos un grado
// revisado) y los grados verificados con enlace a cada lista.
//
// Server Component: no tiene estado, solo pinta. La atribución dudosa se marca
// porque el §2.2 la convierte en un bloqueante de corrección de la ruta del
// acudiente.

import Link from "next/link";
import type { Colegio } from "@tukit/contrato";
import styles from "@/app/colegios/Colegios.module.css";

export default function TarjetaColegio({ colegio }: { colegio: Colegio }) {
  const esAliado = colegio.es_partner ?? colegio.grados.length > 0;
  const id = encodeURIComponent(colegio.colegio_id);

  return (
    <article className={styles.tarjeta}>
      <header className={styles.tarjetaCabecera}>
        {colegio.logo_url ? (
          // Logo del aliado tal como lo sirve identidad. No se usa next/image a
          // propósito: la URL es externa y variable, y el logo es decorativo.
          // eslint-disable-next-line @next/next/no-img-element
          <img className={styles.logo} src={colegio.logo_url} alt="" />
        ) : (
          <span className={styles.logoVacio} aria-hidden="true">
            {colegio.nombre.slice(0, 1)}
          </span>
        )}
        <div className={styles.tarjetaIdentidad}>
          <h2>
            <Link href={`/colegios/${id}`}>{colegio.nombre}</Link>
          </h2>
          <span className={esAliado ? styles.insigniaAliado : styles.insigniaBorrador}>
            {esAliado ? "Aliado" : "Sin listas revisadas"}
          </span>
        </div>
      </header>

      {colegio.atribucion_dudosa ? (
        <p className={styles.avisoAtribucion} role="note">
          Atribución dudosa: comparte plantilla con otro colegio.
        </p>
      ) : null}

      <div className={styles.grados}>
        {colegio.grados.length === 0 ? (
          <p className={styles.sinGrados}>
            Ningún grado revisado.{" "}
            <Link href="/cola">Sube una lista</Link> para empezar.
          </p>
        ) : (
          <ul>
            {colegio.grados.map((grado) => (
              <li key={grado}>
                <Link href={`/colegios/${id}/${encodeURIComponent(grado)}`}>
                  {grado}
                  <span className={styles.gradoEstado}>revisado</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <footer className={styles.tarjetaPie}>
        <span className={styles.fuente}>Fuente: {colegio.fuente}</span>
      </footer>
    </article>
  );
}
