import Link from "next/link";
import { ArrowLeft, Check, Clock } from "lucide-react";
import styles from "../esperando/[trabajo_id]/Espera.module.css";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Recibimos tu lista — Tukit",
};

// La pantalla de verificación (decisión "wait-screen wins"). El acudiente que
// subió al menos un PDF aterriza aquí: cada archivo quedó como una versión
// PENDIENTE de su (colegio, grado) y esperamos a que un administrador la
// apruebe antes de armar su kit. No sondea nada —no hay trabajo que seguir—:
// el aviso llega por correo y celular cuando la lista quede verificada.
//
// Si el hogar además tenía hijos con lista verificada, su kit instantáneo ya
// existe y se enlaza aquí (parámetro `trabajo`), sin quitarle el protagonismo
// a la verificación pendiente.
export default async function Recibimos({
  searchParams,
}: {
  searchParams: Promise<{ pendientes?: string; trabajo?: string }>;
}) {
  const { pendientes, trabajo } = await searchParams;
  const cuantas = Math.max(1, Number(pendientes) || 1);
  const plural = cuantas === 1 ? "tu lista" : `tus ${cuantas} listas`;

  return (
    <div className={styles.pagina}>
      <div className={styles.tarjeta}>
        <span className={styles.chapa}>Recibido</span>
        <h1>Ya tenemos {plural}</h1>

        <p className={styles.honestidad}>
          Nunca armamos un kit con una lista sin verificar. Una persona de Tukit
          revisa {cuantas === 1 ? "la lista que subiste" : "las listas que subiste"} y,
          apenas quede aprobada, te avisamos al correo y al celular con el enlace
          para ver tu kit antes de comprar. Puedes cerrar esta pestaña.
        </p>

        <ol className={styles.etapas}>
          <li className={`${styles.etapa} ${styles.ok}`}>
            <span className={styles.marca} aria-hidden="true">
              <Check size={15} strokeWidth={2.6} />
            </span>
            <div>
              <strong>Recibimos {plural}</strong>
              <span>Leímos el archivo y lo dejamos en la fila de revisión.</span>
            </div>
          </li>
          <li className={`${styles.etapa} ${styles.enCurso}`}>
            <span className={styles.marca} aria-hidden="true">
              <Clock size={15} strokeWidth={2.6} />
            </span>
            <div>
              <strong>Una persona la está revisando</strong>
              <span>
                La pausa que hace que el kit que recibas sea el que alguien dio por
                bueno. Toma un rato, no segundos.
              </span>
            </div>
          </li>
          <li className={styles.etapa}>
            <span className={styles.marca} aria-hidden="true" />
            <div>
              <strong>Te avisamos con tu kit</strong>
              <span>Al correo y al celular, con el enlace para revisarlo antes de comprar.</span>
            </div>
          </li>
        </ol>

        {trabajo && (
          <div className={styles.degradaciones}>
            <strong>Mientras tanto, un kit ya está listo</strong>
            <p style={{ marginTop: "8px" }}>
              Para {cuantas === 1 ? "el otro hijo" : "los hijos"} con lista ya
              verificada del colegio armamos el kit al vuelo. Puedes verlo ahora sin
              esperar la revisión.
            </p>
            <Link
              href={`/esperando/${trabajo}`}
              className={styles.boton}
              style={{ marginTop: "12px" }}
            >
              Ver el kit listo
            </Link>
          </div>
        )}

        <footer className={styles.pie}>
          <span>Te escribimos apenas esté verificada.</span>
          <Link href="/" className={styles.enlacePie}>
            <ArrowLeft size={16} aria-hidden="true" />
            Volver al inicio
          </Link>
        </footer>
      </div>
    </div>
  );
}
