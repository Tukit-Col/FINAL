// Lo que ve quien llega a la consola (o a logistica) y no puede verla. Cada motivo dice que
// hacer: no es lo mismo "entra" que "pidele el rol a un admin" que "el
// servicio esta caido". Server Component: sin estado ni JS en el navegador.

import { urlWeb } from "@tukit/contrato/servidor";
import type { MotivoAcceso } from "@/lib/logistica";
import MarcaTukit from "./MarcaTukit";
import styles from "./AvisoAcceso.module.css";

const TEXTOS: Record<MotivoAcceso, { titulo: string; texto: string; ingresar: boolean }> = {
  sin_sesion: {
    titulo: "Necesitas ingresar",
    texto: "La consola es del equipo interno. Ingresa con tu cuenta de operador o admin.",
    ingresar: true,
  },
  sesion_expirada: {
    titulo: "Tu sesión terminó",
    texto: "Vuelve a ingresar para seguir trabajando en la consola.",
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
  // El texto de verdad es el `mensaje` del 429, que trae la espera.
  limite: {
    titulo: "Danos un momento",
    texto: "Hiciste demasiadas peticiones en poco tiempo. Espera un momento y recarga la página.",
    ingresar: false,
  },
};

export default function AvisoAcceso({ motivo, mensaje }: { motivo: MotivoAcceso; mensaje?: string }) {
  const { titulo, ingresar } = TEXTOS[motivo];
  // Con el limite de tasa manda el mensaje del gateway: dice cuanto esperar.
  const texto = motivo === "limite" && mensaje ? mensaje : TEXTOS[motivo].texto;
  return (
    <>
    {/* Sin sesion no hay cabecera: la marca va aqui. Con sesion ya esta arriba. */}
    {motivo === "sin_sesion" || motivo === "sesion_expirada" ? <MarcaTukit /> : null}
    <section className={styles.aviso} role={motivo === "servicio_caido" ? "alert" : "status"}>
      <h2 className={styles.titulo}>{titulo}</h2>
      <p className={styles.texto}>{texto}</p>
      {ingresar ? (
        <a className={styles.ingresar} href={`${urlWeb()}/ingresar`}>
          Ir a ingresar
        </a>
      ) : null}
    </section>
    </>
  );
}
