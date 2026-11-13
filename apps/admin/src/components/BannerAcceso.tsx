// Banda de ancho completo con lo que salió mal (o el resultado de una acción).
//
// Un 401 (sesión vencida) o un 403 (sin rol) no son un error de formulario:
// son "no puedes seguir aquí", y se leen arriba de la sección, con su salida.
// El texto de un 409/422 es el del backend. Presentacional: la URL de ingreso
// la pone el servidor (el cliente no conoce el origen de la web).

import { claseDeFallo, type ClaseDeFallo } from "@/lib/logistica";
import styles from "./BannerAcceso.module.css";

export interface FalloVisible {
  estado: number;
  mensaje: string;
}

export interface NotaVisible {
  tono: "ok" | "aviso";
  mensaje: string;
}

interface Props {
  fallo?: FalloVisible | null;
  nota?: NotaVisible | null;
  /** Enlace "Volver a ingresar" del 401. */
  urlIngresar?: string;
  onCerrar?: () => void;
}

const TITULO: Record<ClaseDeFallo, string> = {
  sesion: "Tu sesión terminó",
  rol: "Tu rol no permite esto",
  conflicto: "Alguien movió este pedido antes",
  pasarela: "Wompi no respondió",
  otro: "No se pudo completar",
};

export default function BannerAcceso({
  fallo,
  nota,
  urlIngresar,
  onCerrar,
}: Props) {
  if (!fallo && !nota) return null;

  if (fallo) {
    const clase = claseDeFallo(fallo.estado);
    return (
      <div className={`${styles.banda} ${styles.error}`} role="alert">
        <div className={styles.texto}>
          <strong>{TITULO[clase]}</strong>
          <span>
            {clase === "rol"
              ? "Pide el rol de operador a un admin de Tukit. "
              : ""}
            {fallo.mensaje}
          </span>
        </div>
        <div className={styles.acciones}>
          {clase === "sesion" && urlIngresar ? (
            <a className={styles.enlace} href={urlIngresar}>
              Volver a ingresar
            </a>
          ) : null}
          {onCerrar ? (
            <button
              type="button"
              className={styles.cerrar}
              onClick={onCerrar}
              aria-label="Cerrar aviso"
            >
              Cerrar
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`${styles.banda} ${nota!.tono === "ok" ? styles.ok : styles.aviso}`}
      role="status"
    >
      <div className={styles.texto}>
        <span>{nota!.mensaje}</span>
      </div>
      {onCerrar ? (
        <div className={styles.acciones}>
          <button
            type="button"
            className={styles.cerrar}
            onClick={onCerrar}
            aria-label="Cerrar aviso"
          >
            Cerrar
          </button>
        </div>
      ) : null}
    </div>
  );
}
