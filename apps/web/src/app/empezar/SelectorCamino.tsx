import { LogIn, UserPlus } from "lucide-react";
import type { Modo } from "@/lib/formulario-empezar";
import styles from "./Empezar.module.css";

export default function SelectorCamino({
  modo,
  onElegir,
}: {
  modo: Modo;
  onElegir: (modo: Modo) => void;
}) {
  return (
    <div className={styles.dosColumnas} role="group" aria-label="¿Ya tienes cuenta?">
      <button
        type="button"
        aria-pressed={modo === "existente"}
        className={`${styles.opcionEntrada} ${modo === "existente" ? styles.opcionActiva : ""}`}
        onClick={() => onElegir("existente")}
      >
        <LogIn size={16} strokeWidth={2.4} aria-hidden="true" />
        <span className={styles.opcionTexto}>
          <strong>Ya tengo cuenta, ingresar</strong>
          <span>Te precargamos a tus hijos: no vuelves a escribir su colegio ni su grado.</span>
        </span>
      </button>
      <button
        type="button"
        aria-pressed={modo === "nuevo"}
        className={`${styles.opcionEntrada} ${modo === "nuevo" ? styles.opcionActiva : ""}`}
        onClick={() => onElegir("nuevo")}
      >
        <UserPlus size={16} strokeWidth={2.4} aria-hidden="true" />
        <span className={styles.opcionTexto}>
          <strong>Crear cuenta nueva</strong>
          <span>Guardamos tus pedidos y a tus hijos para la próxima vez.</span>
        </span>
      </button>
    </div>
  );
}
