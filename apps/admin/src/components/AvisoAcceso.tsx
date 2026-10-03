// Lo que ve quien llega a logistica y no puede verla. Cada motivo dice que
// hacer: no es lo mismo "entra" que "pidele el rol a un admin" que "el
// servicio esta caido". Server Component: sin estado ni JS en el navegador.

import { urlWeb } from "@tukit/contrato/servidor";
import type { MotivoAcceso } from "@/lib/logistica";
import styles from "./AvisoAcceso.module.css";

const TEXTOS: Record<MotivoAcceso, { titulo: string; texto: string; ingresar: boolean }> = {
  sin_sesion: {
    titulo: "Necesitas ingresar",
    texto: "Logística es del equipo interno. Ingresa con tu cuenta de operador o admin.",
    ingresar: true,
  },
  sesion_expirada: {
    titulo: "Tu sesión terminó",
    texto: "Vuelve a ingresar para seguir moviendo pedidos.",
    ingresar: true,
  },
  sin_rol: {
    titulo: "Esta vista es solo para el equipo interno",
    texto: "Tu cuenta no tiene rol de operador ni de admin. Pídeselo a un admin de Tukit.",
    ingresar: false,
  },
  servicio_caido: {
    titulo: "No pudimos leer los pedidos",
    texto: "Comercio o identidad no responden. Revisa que los servicios estén arriba (make estado).",
    ingresar: false,
  },
};

export default function AvisoAcceso({ motivo }: { motivo: MotivoAcceso }) {
  const { titulo, texto, ingresar } = TEXTOS[motivo];
  return (
    <section className={styles.aviso} role={motivo === "servicio_caido" ? "alert" : "status"}>
      <h2 className={styles.titulo}>{titulo}</h2>
      <p className={styles.texto}>{texto}</p>
      {ingresar ? (
        <a className={styles.ingresar} href={`${urlWeb()}/ingresar`}>
          Ir a ingresar
        </a>
      ) : null}
    </section>
  );
}
