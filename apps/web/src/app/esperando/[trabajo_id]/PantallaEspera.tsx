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
  encolado: "Tu solicitud está en la fila",
  procesando: "Estamos armando tu kit",
  espera_revision: "Recibimos tu solicitud",
  publicado: "Tu kit esta listo",
  fallido: "Algo se rompió",
  cancelado: "Cancelaste esta solicitud",
};

export default function PantallaEspera({
  trabajoId,
  conSesion,
}: {
  trabajoId: string;
  conSesion: boolean;
}) {
  const router = useRouter();
  const [trabajo, setTrabajo] = useState<Trabajo | null>(null);
  const [fallo, setFallo] = useState<FalloApi | null>(null);
  const [segundos, setSegundos] = useState(0);
  // Cada vuelta arranca el sondeo otra vez; la sube el boton que aparece tras
  // un 429, porque el sondeo no lo reintenta solo.
  const [vuelta, setVuelta] = useState(0);

  useEffect(() => {
    const parar = sondear(trabajoId, setTrabajo, setFallo);
    return parar;
  }, [trabajoId, vuelta]);

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

  // 401: el kit es de una cuenta con clave y no hay sesion (o caduco). El sondeo
  // ya paro; se manda a ingresar con /kits como destino de regreso, el mismo que
  // usa la pagina del kit.
  useEffect(() => {
    if (fallo?.estado !== 401) return;
    router.replace(`/ingresar?destino=${encodeURIComponent(`/kits/${trabajoId}`)}`);
  }, [fallo?.estado, router, trabajoId]);

  if (fallo && fallo.estado === 404) {
    return (
      <div className={styles.pagina}>
        <div className={styles.tarjeta}>
          <h1>No encontramos esa solicitud</h1>
          <p>
            El enlace puede estar incompleto o la solicitud ya no existe. Puedes empezar
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
  // Todavia no hay pedido: el pedido nace al pagar (Mis pedidos). Lo que
  // existe aqui es la solicitud del kit, y asi se llama en el panel.
  const chapa = <span className={styles.chapa}>Solicitud {trabajoId.slice(0, 8)}</span>;

  // El 429 del sondeo (cupo de la cuenta agotado): el sondeo no lo reintenta
  // solo, asi que el boton lo arranca otra vez. Sale tambien en la revision,
  // que sigue sondeando hasta que se publique.
  const avisoLimite = fallo?.estado === 429 && (
    <>
      <div className={styles.error} role="alert">
        {fallo.message} Tu solicitud sigue avanzando mientras tanto.
      </div>
      <button
        type="button"
        className={styles.boton}
        onClick={() => {
          setFallo(null);
          setVuelta((v) => v + 1);
        }}
      >
        Consultar de nuevo
      </button>
    </>
  );

  if (enRevision) {
    // La revision humana puede tardar horas: no tiene sentido tener al
    // acudiente mirando una ruedita y un reloj. Se le confirma que la
    // solicitud llego y que le escribimos al terminar (el repartidor de
    // Operacion manda el correo al publicarse el kit).
    return (
      <div className={styles.pagina}>
        <div className={styles.tarjeta}>
          {chapa}
          <span className={`${styles.marca} ${styles.marcaGrande}`} aria-hidden="true">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d="M3.5 8.5l3 3 6-7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <h1>Recibimos tu solicitud</h1>
          <p className={styles.honestidad}>
            Ya armamos tus kits y les estamos dando una última revisión para que
            todo salga bien. Te escribimos al correo apenas estén listos; no
            tienes que quedarte en esta página.
          </p>
          {conSesion ? (
            <p className={styles.honestidad}>
              Mientras tanto, la encuentras en <strong>Mis solicitudes</strong>.
            </p>
          ) : null}
          {avisoLimite}
          <Link href={conSesion ? "/dashboard#solicitudes" : "/"} className={styles.boton}>
            {conSesion ? "Ir a Mis solicitudes" : "Volver al inicio"}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pagina}>
      <div className={styles.tarjeta}>
        {chapa}
        <h1>{ESTADO_TITULO[estado]}</h1>

        <p className={styles.honestidad}>
          Recibimos tu solicitud. Puedes cerrar esta pestaña: te escribimos al
          correo cuando tus kits estén listos.
        </p>

        <ol className={styles.etapas}>
          {ETAPAS.map((nombre) => {
            const etapa = etapas.find((e) => e.nombre === nombre);
            return <FilaEtapa key={nombre} nombre={nombre} etapa={etapa} />;
          })}
          <li className={`${styles.etapa} ${estado === "publicado" ? styles.ok : ""}`}>
            <Marca estado={estado === "publicado" ? "ok" : "pendiente"} />
            <div>
              <strong>Última revisión</strong>
              <span>Le damos una mirada final antes de mostrártelo.</span>
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
            escríbenos: la solicitud queda guardada.
          </div>
        )}

        {avisoLimite}

        <footer className={styles.pie}>
          <span className="cifra">{formatearReloj(segundos)} esperando</span>
          <Link href={conSesion ? "/dashboard" : "/"} className={styles.enlacePie}>
            <ArrowLeft size={16} aria-hidden="true" />
            {conSesion ? "Volver a mi panel" : "Volver al inicio"}
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
