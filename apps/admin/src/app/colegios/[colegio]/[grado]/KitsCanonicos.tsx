// Los 3 kits NSGA aprobados de un grado, en solo-lectura. La fuente es EL
// canónico: el trabajo `publicado` que `_fijar_canonico` fijó al aprobar la
// revisión (la "caché bendita" que el acudiente reusa por la ruta rápida).
// Nunca previews ni trabajos sin aprobar: si el grado no tiene canónico, la
// página no monta este panel.
//
// No reusa `ConsolaRevision` (es de edición): aquí solo se muestran los tres
// puntos del frente de Pareto —perfil, total, disponibilidad— con el recomendado
// marcado, para que el revisor vea de un vistazo qué quedó publicado.
import { formatearPesos, type Kit, type Recomendacion } from "@tukit/contrato";
import styles from "../../Colegios.module.css";

export default function KitsCanonicos({
  kits,
  recomendado,
}: {
  kits: Kit[];
  recomendado: Recomendacion | null;
}) {
  if (kits.length === 0) return null;
  return (
    <ul className={styles.kitsCanonicos}>
      {kits.map((kit) => {
        const esRecomendado = kit.perfil === recomendado?.perfil;
        return (
          <li
            key={kit.perfil}
            className={`${styles.kitCard} ${esRecomendado ? styles.kitCardRecomendado : ""}`}
          >
            <div className={styles.kitCardCabecera}>
              <span className={styles.kitCardPerfil}>{kit.perfil}</span>
              {esRecomendado && <span className={styles.kitCardChapa}>Recomendado</span>}
            </div>
            <span className={`${styles.kitCardTotal} cifra`}>{formatearPesos(kit.total)}</span>
            <span className={styles.kitCardMeta}>
              {Math.round(kit.objetivos.disponibilidad * 100)}% con precio confirmado ·{" "}
              {kit.lineas.length} renglones
            </span>
          </li>
        );
      })}
    </ul>
  );
}
