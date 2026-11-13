import Image from "next/image";
import Link from "next/link";
import { BellRing, MailCheck, PackageCheck } from "lucide-react";
import styles from "./Armado.module.css";

// La pantalla que cierra el armado cuando el kit queda en revision: dice a que
// correo escribimos y que pasa despues. No promete una hora: la revision la
// hace una persona y puede tardar.
export default function ConfirmacionCorreo({
  correo,
  conSesion,
  extra,
}: {
  correo: string | null;
  conSesion: boolean;
  extra?: React.ReactNode;
}) {
  return (
    <div className={styles.confirmacion}>
      <div className={styles.imagenCorreo}>
        <Image
          src="/marca/espera-correo.webp"
          alt="Una caja Tukit abierta con los útiles dentro"
          width={960}
          height={847}
          sizes="(max-width: 700px) 80vw, 300px"
          className={styles.foto}
        />
      </div>
      <div className={styles.cuerpoCorreo}>
        <span className={styles.sello} aria-hidden="true">
          <MailCheck size={22} strokeWidth={2.4} />
        </span>
        <h1>{correo ? "Revisa tu correo" : "Te escribimos al terminar"}</h1>
        <p className={styles.correoLinea}>
          {correo ? (
            <>
              Te escribimos a <strong>{correo}</strong> apenas tus kits estén listos.
            </>
          ) : (
            <>Te escribimos al correo con el que empezaste apenas tus kits estén listos.</>
          )}
        </p>
        <ol className={styles.siguientes}>
          <li>
            <PackageCheck size={18} aria-hidden="true" />
            <span>Una persona revisa tus kits una última vez. No tienes que esperar aquí.</span>
          </li>
          <li>
            <BellRing size={18} aria-hidden="true" />
            <span>Con el correo, abres el enlace, comparas los tres kits y eliges el tuyo.</span>
          </li>
          <li>
            <MailCheck size={18} aria-hidden="true" />
            <span>Si no lo ves en unos minutos, mira en spam o promociones.</span>
          </li>
        </ol>
        {extra}
        <Link href={conSesion ? "/dashboard#solicitudes" : "/"} className={styles.boton}>
          {conSesion ? "Ir a Mis solicitudes" : "Volver al inicio"}
        </Link>
      </div>
    </div>
  );
}
