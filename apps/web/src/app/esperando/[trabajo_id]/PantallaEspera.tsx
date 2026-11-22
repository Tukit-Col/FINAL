"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { type Trabajo } from "@tukit/contrato";
import { FalloApi, sondear } from "@/lib/api-navegador";
import ConfirmacionCorreo from "./ConfirmacionCorreo";
import ProgresoArmado from "./ProgresoArmado";
import styles from "./Espera.module.css";

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
  correo,
}: {
  trabajoId: string;
  conSesion: boolean;
  correo: string | null;
}) {
  const router = useRouter();
  const [trabajo, setTrabajo] = useState<Trabajo | null>(null);
  const [fallo, setFallo] = useState<FalloApi | null>(null);
  const [segundos, setSegundos] = useState(0);
  const [vuelta, setVuelta] = useState(0);

  useEffect(() => {
    const parar = sondear(trabajoId, setTrabajo, setFallo);
    return parar;
  }, [trabajoId, vuelta]);

  useEffect(() => {
    const reloj = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(reloj);
  }, []);

  const llaveVisto = `tukit-espera-vista-${trabajoId}`;
  const yaVisto = useSyncExternalStore(
    () => () => undefined,
    () => {
      try {
        return sessionStorage.getItem(llaveVisto) === "1";
      } catch {
        return false;
      }
    },
    () => null,
  );
  const [recorrido, setRecorrido] = useState(false);
  const estadoActual = trabajo?.estado;
  const alCompletar = useCallback(() => {
    try {
      sessionStorage.setItem(llaveVisto, "1");
    } catch {
    }
    if (estadoActual === "publicado") router.replace(`/kits/${trabajoId}`);
    else setRecorrido(true);
  }, [estadoActual, llaveVisto, router, trabajoId]);

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
  const chapa = <span className={styles.chapa}>Solicitud {trabajoId.slice(0, 8)}</span>;

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

  if (enRevision && recorrido) {
    return (
      <div className={styles.pagina}>
        <div className={styles.tarjeta}>
          {chapa}
          <ConfirmacionCorreo correo={correo} conSesion={conSesion} extra={avisoLimite} />
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
          Puedes cerrar esta pestaña: te escribimos al correo cuando tus kits estén listos.
        </p>

        {yaVisto !== null && (
          <ProgresoArmado
            etapas={etapas}
            terminado={estado === "publicado" || enRevision}
            yaVisto={yaVisto}
            onCompleto={alCompletar}
          />
        )}

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

function formatearReloj(segundos: number): string {
  const m = Math.floor(segundos / 60);
  const s = segundos % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
