import Link from "next/link";
import { ArrowRight, ClipboardList, LifeBuoy, Package } from "lucide-react";
import type { Pedido } from "@tukit/contrato";
import Barras from "@/components/ui/Barras";
import Columnas from "@/components/ui/Columnas";
import Dona from "@/components/ui/Dona";
import Insignia from "@/components/ui/Insignia";
import { haceCuanto } from "@/lib/formato";
import {
  agruparPorDia,
  pedidosPorDia,
  type Actividad,
  type ListasPanel,
} from "@/lib/panel-vivo";
import pulso from "./PanelPulso.module.css";

const ICONO_ACTIVIDAD: Record<Actividad["tipo"], typeof Package> = {
  pedido: Package,
  ticket: LifeBuoy,
  lista: ClipboardList,
};

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

export function PulsoListas({ listas }: { listas: ListasPanel | null }) {
  const gradoTope = listas ? Math.max(...listas.porGrado.map((g) => g.listas), 0) : 0;
  return (
    <div className={pulso.contenedor}>
      {listas === null ? (
        <p className={pulso.vacio}>No pudimos leer las listas pendientes.</p>
      ) : listas.total === 0 ? (
        <p className={pulso.vacio}>No hay listas esperando verificación.</p>
      ) : (
        <>
          <Dona
            compacta
            centro={listas.total === 1 ? "lista" : "listas"}
            segmentos={[
              {
                clave: "esperando",
                etiqueta: "Acudiente esperando",
                valor: listas.esperando,
                href: "/cola?origen=acudiente",
                color: "var(--clay-estrella-oscuro)",
              },
              {
                clave: "colegio",
                etiqueta: "Sin acudiente detrás",
                valor: listas.total - listas.esperando,
                href: "/cola?origen=colegio",
                color: "var(--clay-cielo)",
              },
            ]}
            pie={
              <li className={pulso.pieDona}>
                en {plural(listas.colegios, "colegio", "colegios")}
              </li>
            }
          />

          {listas.porGrado.length > 1 ? (
            <>
              <h3 className={pulso.subtitulo}>Por grado</h3>
              <Columnas
                etiqueta="Listas por verificar por grado"
                alto={44}
                columnas={listas.porGrado.map((g) => ({
                  clave: g.grado,
                  etiqueta: g.grado.slice(0, 3),
                  descripcion: `${g.grado}: ${plural(g.listas, "lista", "listas")}`,
                  valor: g.listas,
                  href: `/cola?grado=${encodeURIComponent(g.grado)}`,
                  realce: g.listas === gradoTope,
                }))}
              />
            </>
          ) : null}

          <h3 className={pulso.subtitulo}>Colegios con más pendientes</h3>
          <Barras
            fina={listas.uniforme}
            maximo={Math.max(...listas.grupos.map((g) => g.listas), 1)}
            filas={[
              ...listas.grupos.map((g) => ({
                clave: g.clave,
                etiqueta: g.nombre,
                valor: g.listas,
                valorTexto: plural(g.listas, "lista", "listas"),
                href: `/cola?q=${encodeURIComponent(g.nombre.slice(0, 80))}`,
                tono: g.esperando > 0 ? ("aviso" as const) : ("normal" as const),
                nota:
                  g.esperando > 0 ? (
                    <Insignia tono="aviso">
                      {g.esperando === 1 ? "acudiente esperando" : `${g.esperando} esperando`}
                    </Insignia>
                  ) : undefined,
              })),
              ...(listas.otros
                ? [
                    {
                      clave: "otros",
                      etiqueta: `Otros ${plural(listas.otros.colegios, "colegio", "colegios")}`,
                      valor: listas.otros.listas,
                      valorTexto: plural(listas.otros.listas, "lista", "listas"),
                      href: "/cola",
                      tono: "suave" as const,
                    },
                  ]
                : []),
            ]}
          />
          <Link href="/cola" className={pulso.secundario}>
            Abrir la cola
            <ArrowRight size={15} strokeWidth={2.4} aria-hidden="true" />
          </Link>
        </>
      )}
    </div>
  );
}

export function PulsoActividad({
  actividad,
  pedidos,
  ahora,
}: {
  actividad: readonly Actividad[];
  pedidos: readonly Pick<Pedido, "creado_en">[] | null;
  ahora: number;
}) {
  const dias = agruparPorDia(actividad, ahora);
  const semana = pedidos ? pedidosPorDia(pedidos, ahora) : null;
  const pedidosSemana = semana?.reduce((t, c) => t + c.valor, 0) ?? 0;
  return (
    <div className={pulso.contenedor}>
      {semana ? (
        <div className={pulso.semana}>
          <p className={pulso.semanaCifra}>
            <span className="cifra">{pedidosSemana}</span>{" "}
            {pedidosSemana === 1 ? "pedido" : "pedidos"} en 7 días
          </p>
          <Columnas
            etiqueta="Pedidos creados por día, últimos 7 días"
            alto={36}
            columnas={semana.map((c, i) => ({
              clave: c.clave,
              etiqueta: c.etiqueta,
              descripcion: `${c.etiquetaLarga}: ${plural(c.valor, "pedido", "pedidos")}`,
              valor: c.valor,
              realce: i === semana.length - 1,
            }))}
          />
        </div>
      ) : null}
      {actividad.length === 0 ? (
        <p className={pulso.vacio}>Todavía no hay movimiento.</p>
      ) : (
        <div className={pulso.linea}>
          {dias.map((d) => (
            <section key={d.clave} aria-label={d.titulo} className={pulso.dia}>
              <h3 className={pulso.subtitulo}>{d.titulo}</h3>
              <ol className={pulso.eventos}>
                {d.items.map((a) => {
                  const Icono = ICONO_ACTIVIDAD[a.tipo];
                  return (
                    <li key={a.clave} className={pulso.evento}>
                      <span className={`${pulso.hito} ${pulso[`hito_${a.tipo}`]}`} aria-hidden="true">
                        <Icono size={14} strokeWidth={2.2} />
                      </span>
                      <Link href={a.enlace} className={pulso.eventoEnlace}>
                        <span className={pulso.eventoCuerpo}>
                          <span className={pulso.eventoTitulo}>
                            <strong>{a.titulo}</strong>
                            <Insignia tono={a.tono}>{a.estado}</Insignia>
                          </span>
                          {a.nota ? (
                            <span className={pulso.eventoNota} title={a.nota}>
                              {a.nota}
                            </span>
                          ) : null}
                        </span>
                        <span className={pulso.eventoLado}>
                          {a.monto ? <span className={`${pulso.monto} cifra`}>{a.monto}</span> : null}
                          <span className={pulso.hace}>{haceCuanto(a.instante, ahora)}</span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </div>
      )}
      <p className={pulso.verTodos}>
        <span>Ver todos:</span>
        <Link href="/logistica">pedidos</Link>
        <Link href="/tickets">tickets</Link>
        <Link href="/cola">listas</Link>
      </p>
    </div>
  );
}
