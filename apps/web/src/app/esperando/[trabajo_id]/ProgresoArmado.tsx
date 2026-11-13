"use client";

// La pantalla de "que esta pasando" al armar el kit: cuatro pasos con nombre,
// el actual enfatizado y la caja de Tukit al lado. Cada paso se ve al menos
// ~1,5 s aunque el backend termine antes (cortesia con tope de ~6 s, ver
// `lib/progreso-espera.ts`); el backend nunca espera por esta animacion.
// "Ver ya" salta el resto en cuanto el trabajo esta terminado.

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { Check, FastForward } from "lucide-react";
import {
  DURACION_PASO_MS,
  PASOS,
  pasosHechosPorBackend,
  siguienteMovimiento,
  type EtapaMinima,
} from "@/lib/progreso-espera";
import styles from "./Armado.module.css";

interface Props {
  etapas: readonly EtapaMinima[];
  /** El backend ya no tiene nada mas que hacer (publicado o en revision). */
  terminado: boolean;
  /** Ya vio este recorrido antes (volvio a la pagina): sin cortesia. */
  yaVisto: boolean;
  /** Los pasos ya se vieron; la pantalla padre decide a donde ir. */
  onCompleto: () => void;
}

export default function ProgresoArmado({ etapas, terminado, yaVisto, onCompleto }: Props) {
  const objetivo = pasosHechosPorBackend(etapas, terminado);
  const [visibles, setVisibles] = useState(yaVisto ? PASOS.length : 0);
  const desde = useRef(0);
  const avisado = useRef(false);

  useEffect(() => {
    desde.current = performance.now();
  }, []);

  useEffect(() => {
    if (visibles >= objetivo) return;
    const { enMs } = siguienteMovimiento(visibles, objetivo, performance.now() - desde.current);
    const t = setTimeout(
      () => {
        desde.current = performance.now();
        setVisibles((v) => Math.min(v + 1, PASOS.length));
      },
      Math.max(enMs ?? DURACION_PASO_MS, 0),
    );
    return () => clearTimeout(t);
  }, [visibles, objetivo]);

  useEffect(() => {
    if (visibles >= PASOS.length && terminado && !avisado.current) {
      avisado.current = true;
      onCompleto();
    }
  }, [visibles, terminado, onCompleto]);

  const actual = Math.min(visibles, PASOS.length - 1);
  const puedeSaltar = terminado && visibles < PASOS.length;

  return (
    <div className={styles.escena}>
      <div className={styles.imagen} aria-hidden="true">
        <Image
          src="/marca/espera-armando.webp"
          alt=""
          width={960}
          height={847}
          sizes="(max-width: 700px) 70vw, 280px"
          priority
          className={styles.foto}
        />
      </div>

      <div className={styles.cuerpo}>
        <p className={styles.estado} role="status" aria-live="polite">
          <span className={styles.numero}>
            Paso {actual + 1} de {PASOS.length}
          </span>
          <strong>{PASOS[actual].titulo}</strong>
        </p>

        <ol className={styles.pasos} aria-label="Lo que estamos haciendo">
          {PASOS.map((paso, i) => {
            const estado = i < visibles ? "hecho" : i === visibles ? "actual" : "futuro";
            return (
              <li
                key={paso.clave}
                className={`${styles.paso} ${styles[estado]}`}
                aria-current={estado === "actual" ? "step" : undefined}
              >
                <span className={styles.punto} aria-hidden="true">
                  {estado === "hecho" ? <Check size={16} strokeWidth={3.4} /> : i + 1}
                </span>
                <span className={styles.texto}>
                  <strong>{paso.titulo}</strong>
                  {estado === "actual" && <span>{paso.detalle}</span>}
                </span>
                {estado === "hecho" && <span className={styles.oculto}>, listo</span>}
              </li>
            );
          })}
        </ol>

        <div className={styles.barra} aria-hidden="true">
          <span className={styles.relleno} style={{ width: `${Math.round((visibles / PASOS.length) * 100)}%` }} />
        </div>

        {puedeSaltar && (
          <button type="button" className={styles.saltar} onClick={() => setVisibles(PASOS.length)}>
            <FastForward size={18} aria-hidden="true" />
            Ver ya
          </button>
        )}
      </div>
    </div>
  );
}
