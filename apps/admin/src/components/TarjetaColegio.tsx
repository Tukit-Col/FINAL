// Tarjeta de un colegio en la BD de colegios y listas (P4). Muestra el logo del
// aliado (si cargó marca), su nombre, si ya es aliado (tiene al menos un grado
// revisado) y sus grados verificados.
//
// La tarjeta ENTERA es clicable hacia la ficha del colegio (patrón "stretched
// link"): el enlace del nombre lleva un `::after` absoluto que cubre la tarjeta.
// Por eso adentro no puede haber otro enlace (un `<a>` no anida en otro `<a>`):
// los grados pasan a ser `<span>` visuales y el CTA de "sube una lista" —que sí
// es un enlace— se movió a la ficha, no vive aquí.
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
            <Link href={`/colegios/${id}`} className={styles.enlaceTarjeta}>
              {colegio.nombre}
            </Link>
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
          // Sin enlace: el detalle (con su CTA para subir lista) se abre al
          // clicar la tarjeta entera; aquí solo se informa el estado.
          <p className={styles.sinGrados}>Ningún grado revisado todavía.</p>
        ) : (
          <ul>
            {colegio.grados.map((grado) => (
              // Chip visual (no enlace): reusa el look de `.grados li` sin ser
              // un `<a>`, para no anidar dentro del enlace de la tarjeta.
              <li key={grado} className={styles.gradoChip}>
                {grado}
                <span className={styles.gradoEstado}>revisado</span>
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
