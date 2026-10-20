import Link from "next/link";
import { ArrowLeft, BellRing, Check, Clock, MailCheck } from "lucide-react";
import { cuantasDiferidas } from "@/lib/recibimos";
import espera from "../esperando/[trabajo_id]/Espera.module.css";
import styles from "./Recibimos.module.css";

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
//
// Con el catálogo caído la subida igual responde (ADR 0040): la lista queda
// guardada en Tukit y pasa sola a la fila de revisión cuando el catálogo
// vuelve. Esas llegan como `diferidas` y la pantalla le dice al acudiente que
// no tiene que volver a subirlas.
export default async function Recibimos({
  searchParams,
}: {
  searchParams: Promise<{ pendientes?: string; diferidas?: string; trabajo?: string }>;
}) {
  const { pendientes, diferidas: crudas, trabajo } = await searchParams;
  const cuantas = Math.max(1, Number(pendientes) || 1);
  const plural = cuantas === 1 ? "tu lista" : `tus ${cuantas} listas`;
  const diferidas = cuantasDiferidas(crudas, cuantas);
  const cuales =
    cuantas === 1
      ? "tu lista"
      : diferidas === cuantas
        ? `tus ${cuantas} listas`
        : diferidas === 1
          ? "una de tus listas"
          : `${diferidas} de tus listas`;
  const pasa = diferidas === 1 ? "quedó guardada y pasa sola" : "quedaron guardadas y pasan solas";

  return (
    <div className={espera.pagina}>
      <div className={espera.tarjeta}>
        <div className={styles.hero}>
          <span className={styles.sello} aria-hidden="true">
            <MailCheck size={30} strokeWidth={2.2} />
          </span>
          <span className={espera.chapa}>Recibido</span>
          <h1 className={styles.titulo}>Ya tenemos {plural}</h1>
          <p className={styles.entrada}>
            {cuantas === 1
              ? "Quedó a salvo en la fila de revisión."
              : `Las ${cuantas} quedaron a salvo en la fila de revisión.`}{" "}
            Ahora el trabajo es nuestro.
          </p>
        </div>

        <p className={espera.honestidad}>
          Nunca armamos un kit con una lista sin verificar. Una persona de Tukit
          revisa {cuantas === 1 ? "la lista que subiste" : "las listas que subiste"} y,
          apenas quede aprobada, te avisamos al correo y al celular con el enlace
          para ver tu kit antes de comprar. Puedes cerrar esta pestaña.
        </p>

        {diferidas > 0 && (
          <div className={espera.degradaciones} role="status">
            <strong>Pasa a revisión en unos minutos</strong>
            <p style={{ marginTop: "8px" }}>
              Nuestro catálogo tardó en responder, así que {cuales} {pasa} a la fila de
              revisión apenas vuelva. No tienes que volver a{" "}
              {diferidas === 1 ? "subirla" : "subirlas"}.
            </p>
          </div>
        )}

        <ol className={espera.etapas}>
          <li className={`${espera.etapa} ${espera.ok}`}>
            <span className={espera.marca} aria-hidden="true">
              <Check size={15} strokeWidth={2.6} />
            </span>
            <div>
              <strong>Recibimos {plural}</strong>
              <span>Leímos el archivo y lo dejamos en la fila de revisión.</span>
            </div>
          </li>
          <li className={`${espera.etapa} ${espera.enCurso}`}>
            <span className={espera.marca} aria-hidden="true">
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
          <li className={espera.etapa}>
            <span className={espera.marca} aria-hidden="true">
              <BellRing size={15} strokeWidth={2.6} />
            </span>
            <div>
              <strong>Te avisamos con tu kit</strong>
              <span>Al correo y al celular, con el enlace para revisarlo antes de comprar.</span>
            </div>
          </li>
        </ol>

        {trabajo && (
          <div className={espera.degradaciones}>
            <strong>Mientras tanto, un kit ya está listo</strong>
            <p style={{ marginTop: "8px" }}>
              Para {cuantas === 1 ? "el otro hijo" : "los hijos"} con lista ya
              verificada del colegio armamos el kit al vuelo. Puedes verlo ahora sin
              esperar la revisión.
            </p>
            <Link
              href={`/esperando/${trabajo}`}
              className={espera.boton}
              style={{ marginTop: "12px" }}
            >
              Ver el kit listo
            </Link>
          </div>
        )}

        <footer className={espera.pie}>
          <span>Te escribimos apenas esté verificada.</span>
          <Link href="/" className={espera.enlacePie}>
            <ArrowLeft size={16} aria-hidden="true" />
            Volver al inicio
          </Link>
        </footer>
      </div>
    </div>
  );
}
