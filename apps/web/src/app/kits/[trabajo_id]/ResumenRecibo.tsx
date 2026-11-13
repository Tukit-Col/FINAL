import { Check } from "lucide-react";
import estilos from "./ResumenRecibo.module.css";

// Port a React de `receipt` (sf-design-stack): el resumen del kit como un
// tiquete. Cada categoria es un renglon con su marca, una linea de corte
// punteada y el total. Es solo presentacion: los conteos y el total ya vienen
// calculados por VistaKits; aqui no se suma ni se cambia nada. Los renglones
// "se marcan" en cascada una sola vez al montar (CSS puro); con
// prefers-reduced-motion aparece todo de una.

export interface RenglonResumen {
  clave: string;
  titulo: string;
  cantidad: number;
}

export default function ResumenRecibo({
  perfil,
  renglones,
  total,
}: {
  perfil: string;
  renglones: RenglonResumen[];
  total: string;
}) {
  if (renglones.length === 0) return null;
  return (
    <section className={estilos.tiquete} aria-labelledby="resumen-kit-titulo">
      <h2 id="resumen-kit-titulo" className={estilos.titulo}>
        Resumen del kit {perfil}
      </h2>
      <ul className={estilos.lista}>
        {renglones.map((r, i) => (
          <li key={r.clave} className={estilos.renglon} style={{ ["--i" as string]: i }}>
            <span className={estilos.marca} aria-hidden="true">
              <Check size={12} strokeWidth={3.4} />
            </span>
            <span className={estilos.nombre}>{r.titulo}</span>
            <span className={`${estilos.cantidad} cifra`}>
              {r.cantidad} {r.cantidad === 1 ? "producto" : "productos"}
            </span>
          </li>
        ))}
      </ul>
      <div className={estilos.total}>
        <span>Total</span>
        <strong className="cifra">{total}</strong>
      </div>
    </section>
  );
}
