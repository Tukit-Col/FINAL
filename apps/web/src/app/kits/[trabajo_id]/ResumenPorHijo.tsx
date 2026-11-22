import { useState } from "react";
import { CircleAlert, ChevronDown, ChevronUp } from "lucide-react";
import {
  formatearPesos,
  hayQueCobrar,
  personajesPorHijo,
  type LineaKit,
  type Kit,
} from "@tukit/contrato";
import {
  categoriaDeLinea,
  personajeLegible,
  fotoDeConsolidacion,
  textoDeConsolidacion,
  type ResumenHijo,
} from "@/lib/kit-vista";
import styles from "./Kits.module.css";
import { ICONO_CATEGORIA, MiniaturasHijo, TarjetasFan } from "./FranjaFan";

export default function ResumenPorHijo({
  kit,
  resumen,
  nombresHijos,
  gradosHijos,
  pedidos,
}: {
  kit: Kit;
  resumen: ResumenHijo[];
  nombresHijos: Map<string, string>;
  gradosHijos: Map<string, string>;
  pedidos?: Record<string, string[]>;
}) {
  const [colapsados, setColapsados] = useState<Set<string>>(new Set());
  const alternar = (hijo: string) =>
    setColapsados((prev) => {
      const siguiente = new Set(prev);
      if (siguiente.has(hijo)) siguiente.delete(hijo);
      else siguiente.add(hijo);
      return siguiente;
    });
  const conPersonaje = new Map<string, LineaKit[]>();
  for (const g of personajesPorHijo(kit.lineas, pedidos)) {
    conPersonaje.set(g.hijo, [...(conPersonaje.get(g.hijo) ?? []), ...g.lineas]);
  }
  const ahorroTotal = kit.consolidaciones.reduce((n, c) => n + (c.ahorro > 0 ? c.ahorro : 0), 0);

  return (
    <section className={styles.familia} aria-labelledby="titulo-familia">
      <h2 id="titulo-familia" className={styles.familiaTitulo}>
        El kit de cada hijo
      </h2>
      <div className={styles.hijos}>
        {resumen.map((r) => {
          const abierto = !colapsados.has(r.hijo);
          const fan = conPersonaje.get(r.hijo) ?? [];
          const idsFan = new Set(fan.map((l) => l.item_id));
          const otros = r.productos.filter((l) => !idsFan.has(l.item_id));
          const meta = [
            `${r.renglones} ${r.renglones === 1 ? "útil" : "útiles"} de su lista`,
            r.comparten > 0 ? `${r.comparten} ${r.comparten === 1 ? "compartido" : "compartidos"}` : null,
            r.aparte > 0 ? `${r.aparte} por fuera de Tukit` : null,
          ].filter(Boolean);
          return (
            <article key={r.hijo} className={styles.tarjetaHijo}>
              <button
                type="button"
                className={styles.cabezaHijo}
                aria-expanded={abierto}
                onClick={() => alternar(r.hijo)}
              >
                <span className={styles.inicialHijo} aria-hidden="true">
                  {r.nombre.trim().charAt(0).toUpperCase()}
                </span>
                <span className={styles.identidadHijo}>
                  <span className={styles.nombreHijo}>{r.nombre}</span>
                  <span className={styles.datosHijo}>
                    {[r.grado, r.personaje ? personajeLegible(r.personaje) : null].filter(Boolean).join(" · ")}
                  </span>
                </span>
                <span className={styles.totalHijo}>
                  <span className="cifra">{hayQueCobrar(r.total) ? formatearPesos(r.total) : "—"}</span>
                  <span className={styles.metaHijo}>{meta.join(" · ")}</span>
                </span>
                {abierto ? (
                  <ChevronUp size={18} aria-hidden="true" className={styles.chevronHijo} />
                ) : (
                  <ChevronDown size={18} aria-hidden="true" className={styles.chevronHijo} />
                )}
              </button>
              {abierto && (
                <div className={styles.cuerpoHijo}>
                  {fan.length > 0 && (
                    <>
                      <h3 className={styles.subtituloHijo}>
                        Con {r.personaje ? personajeLegible(r.personaje) : "su personaje"}
                      </h3>
                      <TarjetasFan lineas={fan} veces={r.veces} />
                    </>
                  )}
                  {otros.length > 0 && (
                    <>
                      <h3 className={styles.subtituloHijo}>
                        {fan.length > 0 ? "El resto de su lista" : "Su lista"}
                      </h3>
                      <MiniaturasHijo lineas={otros} />
                    </>
                  )}
                  {r.productos.length === 0 && r.falta.length === 0 && (
                    <p className={styles.metaHijo}>
                      Nada de su lista se compra en Tukit: abajo está qué conseguir y dónde.
                    </p>
                  )}
                  {r.falta.length > 0 && (
                    <ul className={styles.faltaHijo} aria-label={`Lo que falta para ${r.nombre}`}>
                      {r.falta.map((aviso, i) => (
                        <li key={i}>
                          <CircleAlert size={15} aria-hidden="true" /> {aviso}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {kit.consolidaciones.length > 0 && (
        <div className={styles.compartido} aria-labelledby="titulo-compartido">
          <div className={styles.compartidoCabeza}>
            <h3 id="titulo-compartido">Lo que comparten</h3>
            <p>
              Son iguales para varios de tus hijos: los compramos juntos y sobra menos.
              {ahorroTotal > 0 && (
                <>
                  {" "}
                  <strong className={styles.ahorroJunto}>Ahorras {formatearPesos(ahorroTotal)}.</strong>
                </>
              )}
            </p>
          </div>
          <ul className={styles.compartidoLista}>
            {kit.consolidaciones.map((c, i) => {
              const t = textoDeConsolidacion(c, nombresHijos, c.ahorro > 0 ? formatearPesos(c.ahorro) : null, gradosHijos);
              const { imagen_url, linea } = fotoDeConsolidacion(kit.lineas, c);
              const Icono = linea ? ICONO_CATEGORIA[categoriaDeLinea(linea)] : CircleAlert;
              return (
                <li key={`${c.producto}-${i}`} className={styles.compartidoItem}>
                  {imagen_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img className={styles.compartidoFoto} src={imagen_url} alt="" loading="lazy" />
                  ) : (
                    <span className={styles.compartidoFoto} aria-hidden="true">
                      <Icono size={26} strokeWidth={1.8} />
                    </span>
                  )}
                  <span className={styles.compartidoTexto}>
                    <strong>{c.producto}</strong>
                    <span>{[t.paraQuienes, t.cantidad].filter(Boolean).join(" · ")}</span>
                  </span>
                  {t.ahorro && <span className={`${styles.compartidoAhorro} cifra`}>−{formatearPesos(c.ahorro)}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
