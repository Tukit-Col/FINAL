"use client";

import { useState } from "react";
import { FileUp, X } from "lucide-react";
import type { Colegio } from "@tukit/contrato";
import FormularioOnboarding from "@/components/FormularioOnboarding";
import styles from "./Cola.module.css";

interface Props {
  colegios: Colegio[];
}

export default function SubirLista({ colegios }: Props) {
  const [abierto, setAbierto] = useState(false);

  return (
    <div className={styles.subirLista}>
      <button
        type="button"
        className={styles.subirBoton}
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
      >
        {abierto ? <X size={16} aria-hidden="true" /> : <FileUp size={16} aria-hidden="true" />}
        {abierto ? "Cerrar" : "Subir lista"}
      </button>

      {abierto ? (
        <div className={styles.subirPanel}>
          <p className={styles.bajada}>
            Sube el PDF de un grado y déjalo percibir. Al terminar entras al revisor de cuatro
            paneles para verificar la lista antes de que la vea un acudiente.
          </p>
          <FormularioOnboarding colegios={colegios} />
        </div>
      ) : null}
    </div>
  );
}
