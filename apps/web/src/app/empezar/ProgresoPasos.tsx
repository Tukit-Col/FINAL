import { Check } from "lucide-react";
import MarcoForma from "@/components/MarcoForma";
import estilos from "./ProgresoPasos.module.css";

export interface PasoProgreso {
  clave: string;
  titulo: string;
  estado: "completo" | "actual" | "futuro";
}

export default function ProgresoPasos({ pasos }: { pasos: PasoProgreso[] }) {
  const total = pasos.length;
  const hechos = pasos.filter((p) => p.estado === "completo").length;
  const actual = pasos.find((p) => p.estado === "actual");
  const numeroActual = actual ? pasos.indexOf(actual) + 1 : total;
  const porcentaje = Math.round((hechos / total) * 100);

  return (
    <MarcoForma className={estilos.panel}>
      <div className={estilos.fila}>
        <p className={estilos.resumen} role="status" aria-live="polite">
          <strong>
            Paso {numeroActual} de {total}
          </strong>
          {actual ? <span>{actual.titulo}</span> : null}
        </p>
      </div>
      <ol className={estilos.lista} aria-label="Progreso del formulario">
        {pasos.map((p, i) => (
          <li
            key={p.clave}
            className={`${estilos.paso} ${estilos[p.estado]}`}
            aria-current={p.estado === "actual" ? "step" : undefined}
          >
            <span className={estilos.punto} aria-hidden="true">
              {p.estado === "completo" ? <Check size={14} strokeWidth={3.4} /> : i + 1}
            </span>
            <span className={estilos.titulo}>{p.titulo}</span>
            {p.estado === "completo" && <span className={estilos.oculto}>, completo</span>}
          </li>
        ))}
      </ol>
      <div className={estilos.barra} aria-hidden="true">
        <span className={estilos.relleno} style={{ width: `${porcentaje}%` }} />
      </div>
    </MarcoForma>
  );
}
