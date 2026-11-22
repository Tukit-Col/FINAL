import Link from "next/link";
import { Check } from "lucide-react";
import { reglasDeClave } from "@tukit/contrato";
import styles from "./Empezar.module.css";

export interface PropsSeccion {
  className: string;
  "aria-current"?: "step";
}

export default function SeccionRegistro({
  propsSeccion,
  idBase,
  idReglasClave,
  correo,
  onCorreo,
  clave,
  onClave,
  celular,
  onCelular,
  aceptaTerminos,
  onAceptaTerminos,
}: {
  propsSeccion: PropsSeccion;
  idBase: string;
  idReglasClave: string;
  correo: string;
  onCorreo: (valor: string) => void;
  clave: string;
  onClave: (valor: string) => void;
  celular: string;
  onCelular: (valor: string) => void;
  aceptaTerminos: boolean;
  onAceptaTerminos: (valor: boolean) => void;
}) {
  return (
    <section {...propsSeccion} aria-labelledby={`${idBase}-registro`}>
      <h2 id={`${idBase}-registro`} className={styles.tituloBloque}>
        <span className={styles.paso}>1</span> Regístrate
      </h2>
      <p className={styles.explicacion}>
        Creamos tu cuenta para guardar tus pedidos y avisarte cuando el kit esté
        listo. La próxima vez entras y ya tienes a tus hijos cargados.
      </p>
      <div className={styles.dosColumnas}>
        <label className={styles.campo}>
          <span>Correo</span>
          <input
            type="email"
            value={correo}
            onChange={(e) => onCorreo(e.target.value)}
            placeholder="tucorreo@ejemplo.com"
            autoComplete="email"
            required
          />
        </label>
        <div className={styles.campo}>
          <label htmlFor={`${idReglasClave}-clave`}>
            <span>Contraseña</span>
          </label>
          <input
            id={`${idReglasClave}-clave`}
            type="password"
            value={clave}
            onChange={(e) => onClave(e.target.value)}
            placeholder="Elige una contraseña"
            autoComplete="new-password"
            aria-describedby={idReglasClave}
            required
          />
          <ul id={idReglasClave} className={styles.reglasClave} aria-live="polite">
            {reglasDeClave(clave).map((regla) => (
              <li key={regla.id} className={regla.cumple ? styles.reglaCumple : styles.reglaPendiente}>
                <Check size={13} aria-hidden="true" strokeWidth={3} />
                {regla.texto}
                <span className={styles.soloLectores}>{regla.cumple ? " (listo)" : " (falta)"}</span>
              </li>
            ))}
          </ul>
        </div>
        <label className={styles.campo}>
          <span>Celular</span>
          <input
            type="tel"
            value={celular}
            onChange={(e) => onCelular(e.target.value)}
            placeholder="+57 300 123 4567"
            autoComplete="tel"
            required
          />
        </label>
      </div>
      <label className={styles.casillaTerminos}>
        <input
          type="checkbox"
          checked={aceptaTerminos}
          onChange={(e) => onAceptaTerminos(e.target.checked)}
          required
        />
        <span>
          Leí y acepto la{" "}
          <Link href="/legal/privacidad" target="_blank" rel="noopener noreferrer">
            política de tratamiento de datos personales
          </Link>{" "}
          y los{" "}
          <Link href="/legal/terminos" target="_blank" rel="noopener noreferrer">
            términos y condiciones
          </Link>
          .
        </span>
      </label>
    </section>
  );
}
