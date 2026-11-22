import type { PropsSeccion } from "./SeccionRegistro";
import styles from "./Empezar.module.css";

export default function SeccionContacto({
  propsSeccion,
  idBase,
  numeroPaso,
  correoSesion,
}: {
  propsSeccion: PropsSeccion;
  idBase: string;
  numeroPaso: number;
  correoSesion: string | undefined;
}) {
  return (
    <section {...propsSeccion} aria-labelledby={`${idBase}-contacto`}>
      <h2 id={`${idBase}-contacto`} className={styles.tituloBloque}>
        <span className={styles.paso}>{numeroPaso}</span> A dónde te avisamos
      </h2>
      <p className={styles.explicacion}>
        Armar el kit toma minutos, no segundos, porque una persona revisa cada
        lista para que la calidad no falle. No tienes que quedarte mirando la
        pantalla: te escribimos cuando esté listo.
      </p>
      <p className={styles.explicacion}>
        Te avisamos a los datos de tu cuenta
        {correoSesion ? (
          <>
            : <strong>{correoSesion}</strong>
          </>
        ) : null}
        .
      </p>
    </section>
  );
}
