import Link from "next/link";
import type { Colegio } from "@tukit/contrato";
import LogoColegio from "@/components/LogoColegio";
import styles from "@/app/colegios/Colegios.module.css";

export default function TarjetaColegio({ colegio, logo }: { colegio: Colegio; logo: string | null }) {
  const esAliado = colegio.es_partner ?? colegio.grados.length > 0;
  const id = encodeURIComponent(colegio.colegio_id);

  return (
    <article className={styles.tarjeta}>
      <header className={styles.tarjetaCabecera}>
        <LogoColegio
          src={logo}
          nombre={colegio.nombre}
          claseImagen={styles.logo}
          claseIniciales={styles.logoVacio}
        />
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
          <p className={styles.sinGrados}>Ningún grado revisado todavía.</p>
        ) : (
          <ul>
            {colegio.grados.map((grado) => (
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
