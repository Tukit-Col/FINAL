import { Check } from "lucide-react";
import estilos from "./ResumenRecibo.module.css";

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
