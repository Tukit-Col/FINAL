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
