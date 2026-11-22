// Los kits aprobados de un grado, en solo lectura.
//
// Decisiones:
// - La fuente es el canónico: el trabajo `publicado` que se fijó al aprobar la revisión. Nunca previews ni
//   trabajos sin aprobar; si el grado no tiene canónico, la página no monta este panel.
// - Editar es "Editar kits", que abre una versión nueva. Sin "Recomendado": el canónico no tiene
//   acudiente ni preferencias, así que el optimizador no recomienda nada real.

"use client";

import { useState } from "react";
import { clasificar, formatearPesos, type Kit } from "@tukit/contrato";
import MatrizComparacion from "@/components/MatrizComparacion";
import styles from "../../Colegios.module.css";

const POR_RESOLVER = new Set(["sin_match", "hueco", "pendiente_revision"]);

export default function KitsCanonicos({ trabajoId, kits }: { trabajoId: string; kits: Kit[] }) {
  const [abierto, setAbierto] = useState(false);
  if (kits.length === 0) return null;

  return (
    <>
      <ul className={styles.kitsCanonicos}>
        {kits.map((kit) => {
          const faltan = kit.lineas.filter((l) => POR_RESOLVER.has(clasificar(l))).length;
          return (
            <li key={kit.perfil} className={styles.kitCard}>
              <div className={styles.kitCardCabecera}>
                <span className={styles.kitCardPerfil}>{kit.perfil}</span>
              </div>
              <span className={`${styles.kitCardTotal} cifra`}>{formatearPesos(kit.total)}</span>
              <span className={styles.kitCardMeta}>
                {Math.round(kit.objetivos.disponibilidad * 100)}% con precio confirmado ·{" "}
                {kit.lineas.length} renglones
                {faltan > 0 ? ` · ${faltan} sin resolver` : ""}
              </span>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        className={`${styles.botonSecundario} ${styles.verItems}`}
        aria-expanded={abierto}
        onClick={() => setAbierto((previo) => !previo)}
      >
        {abierto ? "Ocultar ítems" : "Ver ítems"}
      </button>

      {abierto ? (
        <MatrizComparacion
          trabajoId={trabajoId}
          kits={kits}
          recomendado={undefined}
          sinRotuloRecomendado
          soloLectura
        />
      ) : null}
    </>
  );
}
