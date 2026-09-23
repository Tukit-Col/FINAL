"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { ETAPAS, type Etapa, type NombreEtapa, type Trabajo } from "@tukit/contrato";
import { FalloApi, sondear } from "@/lib/api-navegador";
import styles from "./Espera.module.css";

// Que hace cada etapa, dicho como se lo diria una persona a otra. Los nombres
// tecnicos del contrato no le dicen nada a un papa, pero el ORDEN si le dice
// algo: sirve para saber cuanto falta.
const EXPLICACION: Record<NombreEtapa, { titulo: string; detalle: string }> = {
  percepcion: {
    titulo: "Leyendo la lista",
    detalle: "Sacando renglón por renglón lo que pide el colegio.",
  },
  normalizacion: {
    titulo: "Entendiendo qué es cada cosa",
    detalle: "Un esfero y un bolígrafo son lo mismo; un cuaderno de 100 hojas no es cualquiera.",
  },
  resolucion: {
    titulo: "Buscando cada producto",
    detalle: "Es la parte lenta, y es a propósito: preferimos acertar a ir rápido.",
  },
  optimizacion: {
    titulo: "Armando los tres kits",
    detalle: "Juntando lo repetido entre hermanos y comparando precio entre tiendas.",
  },
};

const ESTADO_TITULO: Record<Trabajo["estado"], string> = {
  encolado: "Tu pedido está en la fila",
  procesando: "Estamos armando tu kit",
  espera_revision: "Una persona lo está revisando",
  publicado: "Tu kit esta listo",
  fallido: "Algo se rompió",
};

export default function PantallaEspera({ trabajoId }: { trabajoId: string }) {
  const router = useRouter();
  const [trabajo, setTrabajo] = useState<Trabajo | null>(null);
  const [fallo, setFallo] = useState<FalloApi | null>(null);
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    const parar = sondear(trabajoId, setTrabajo, setFallo);
    return parar;
  }, [trabajoId]);

  useEffect(() => {
    const reloj = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(reloj);
  }, []);

  useEffect(() => {
    // Publicado se sale de esta pantalla solo. Se espera un momento para que
    // la ultima etapa alcance a verse marcada: pasar de golpe deja la
    // sensacion de que algo se salto.
    if (trabajo?.estado !== "publicado") return;
    const salto = setTimeout(() => router.replace(`/kits/${trabajoId}`), 900);
    return () => clearTimeout(salto);
  }, [trabajo?.estado, router, trabajoId]);

  if (fallo && fallo.estado === 404) {
    return (
      <div className={styles.pagina}>
        <div className={styles.tarjeta}>
          <h1>No encontramos ese pedido</h1>
          <p>
            El enlace puede estar incompleto o el pedido ya no existe. Puedes empezar
            uno nuevo.
          </p>
          <Link href="/empezar" className={styles.boton}>
            Armar mi kit
          </Link>
        </div>
      </div>
    );
  }

  const estado = trabajo?.estado ?? "encolado";
  const etapas = trabajo?.etapas ?? [];
  const enRevision = estado === "espera_revision";

  return (
    <div className={styles.pagina}>
      <div className={styles.tarjeta}>
        <span className={styles.chapa}>Pedido {trabajoId.slice(0, 8)}</span>
        <h1>{ESTADO_TITULO[estado]}</h1>

        <p className={styles.honestidad}>
          {enRevision
            ? "Ya terminamos la parte automática. Ahora alguien de Tukit mira lo que quedó dudoso antes de mostrártelo: nunca te mandamos un kit sin revisar."
            : "Esto toma minutos, no segundos. Puedes cerrar esta pestaña: te avisamos al correo y al celular cuando esté listo."}
        </p>

        <ol className={styles.etapas}>
          {ETAPAS.map((nombre) => {
            const etapa = etapas.find((e) => e.nombre === nombre);
            return <FilaEtapa key={nombre} nombre={nombre} etapa={etapa} />;
          })}
          <li
            className={`${styles.etapa} ${
              enRevision ? styles.enCurso : estado === "publicado" ? styles.ok : ""
            }`}
          >
            <Marca estado={enRevision ? "en_curso" : estado === "publicado" ? "ok" : "pendiente"} />
            <div>
              <strong>Revisión de una persona</strong>
              <span>
                La pausa que hace que el kit que recibes sea el que alguien dio por
                bueno.
              </span>
            </div>
          </li>
        </ol>

        {trabajo?.degradaciones && trabajo.degradaciones.length > 0 && (
          <div className={styles.degradaciones}>
            <strong>Cosas que no salieron perfectas y preferimos contarte:</strong>
            <ul>
              {trabajo.degradaciones.map((d) => (
                <li key={d.dependencia}>
                  {d.efecto} · {d.lineas_afectadas}{" "}
                  {d.lineas_afectadas === 1 ? "renglón" : "renglones"}
                </li>
              ))}
            </ul>
          </div>
        )}

        {estado === "fallido" && (
          <div className={styles.error} role="alert">
            No pudimos terminar tu kit. Vuelve a intentarlo y, si sigue igual,
            escríbenos: el pedido queda guardado.
          </div>
        )}

        <footer className={styles.pie}>
          <span className="cifra">{formatearReloj(segundos)} esperando</span>
          <Link href="/" className={styles.enlacePie}>
            <ArrowLeft size={16} aria-hidden="true" />
            Volver al inicio
          </Link>
        </footer>
      </div>
    </div>
  );
}

function FilaEtapa({ nombre, etapa }: { nombre: NombreEtapa; etapa: Etapa | undefined }) {
  const estado = etapa?.estado ?? "pendiente";
  const texto = EXPLICACION[nombre];
  return (
    <li
      className={`${styles.etapa} ${
        estado === "ok" ? styles.ok : estado === "en_curso" ? styles.enCurso : ""
      } ${estado === "fallida" ? styles.fallida : ""}`}
    >
      <Marca estado={estado} />
      <div>
        <strong>{texto.titulo}</strong>
        <span>{texto.detalle}</span>
        {estado === "incompleta" && (
          <em className={styles.incompleta}>
            Quedó a medias y va a revisión. No recortamos nada en silencio.
          </em>
        )}
      </div>
      {etapa && estado === "ok" && (
        <span className={`${styles.ms} cifra`}>{(etapa.ms / 1000).toFixed(1)} s</span>
      )}
    </li>
  );
}

function Marca({ estado }: { estado: Etapa["estado"] }) {
  if (estado === "ok") {
    return (
      <span className={styles.marca} aria-hidden="true">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4">
          <path d="M3.5 8.5l3 3 6-7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (estado === "en_curso") {
    return <span className={`${styles.marca} ${styles.girando}`} aria-hidden="true" />;
  }
  return <span className={styles.marca} aria-hidden="true" />;
}

function formatearReloj(segundos: number): string {
  const m = Math.floor(segundos / 60);
  const s = segundos % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
