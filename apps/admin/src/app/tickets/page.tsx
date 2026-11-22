import Form from "next/form";
import Link from "next/link";
import type { BandejaOperacion } from "@tukit/contrato";
import {
  casoActivo,
  ETIQUETA_CATEGORIA_CASO,
  ETIQUETA_PRIORIDAD,
  ORDEN_PRIORIDAD,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import AvisoAcceso from "@/components/AvisoAcceso";
import TarjetaTicket from "@/components/TarjetaTicket";
import { motivoDeFallo } from "@/lib/logistica";
import { quienSoy, tokenDeSesion } from "@/lib/sesion";
import {
  ESTADOS_TICKET,
  ETIQUETA_ESTADO_TICKET,
  filtrarCasos,
  hayFiltrosTickets,
  hrefTickets,
  instanteActual,
  leerFiltrosTickets,
  paginar,
} from "@/lib/tickets";
import Chip, { Chips } from "@/components/ui/Chip";
import EstadoVacio from "@/components/ui/EstadoVacio";
import styles from "./Tickets.module.css";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const CATEGORIAS = Object.keys(
  ETIQUETA_CATEGORIA_CASO,
) as (keyof typeof ETIQUETA_CATEGORIA_CASO)[];
const PRIORIDADES = Object.keys(
  ORDEN_PRIORIDAD,
) as (keyof typeof ORDEN_PRIORIDAD)[];

function Encabezado() {
  return (
    <header className={styles.encabezado}>
      <h1>Tickets</h1>
    </header>
  );
}

export default async function PaginaTickets({ searchParams }: Props) {
  const token = await tokenDeSesion();
  if (!token) {
    return (
      <div className={styles.pagina}>
        <Encabezado />
        <AvisoAcceso motivo="sin_sesion" />
      </div>
    );
  }

  let bandeja: BandejaOperacion;
  try {
    bandeja = await origenDeDatos().casos(token);
  } catch (causa) {
    if (!(causa instanceof ErrorTukit)) throw causa;
    return (
      <div className={styles.pagina}>
        <Encabezado />
        <AvisoAcceso motivo={motivoDeFallo(causa.estado)} />
      </div>
    );
  }
  const { resumen } = bandeja;
  const filtros = leerFiltrosTickets(await searchParams);
  const ahora = instanteActual();
  const yo = (await quienSoy())?.usuarioId ?? null;
  const casos = filtrarCasos(bandeja.casos, filtros, ahora, yo);

  const ordenados = [...casos].sort((a, b) => {
    const activoA = casoActivo(a) ? 0 : 1;
    const activoB = casoActivo(b) ? 0 : 1;
    const venceA = a.vence_en
      ? new Date(a.vence_en).getTime()
      : Number.POSITIVE_INFINITY;
    const venceB = b.vence_en
      ? new Date(b.vence_en).getTime()
      : Number.POSITIVE_INFINITY;
    return (
      activoA - activoB ||
      ORDEN_PRIORIDAD[a.prioridad] - ORDEN_PRIORIDAD[b.prioridad] ||
      (venceA === venceB ? 0 : venceA < venceB ? -1 : 1) ||
      (a.abierto_en < b.abierto_en ? 1 : -1)
    );
  });
  const pagina = paginar(ordenados, filtros.pagina);

  const chips = [
    {
      clave: "abiertos",
      etiqueta: "Abiertos",
      valor: resumen.abiertos,
      href: hrefTickets(filtros, {
        pagina: 1,
        vencidos: false,
        asignado: "",
        prioridad: "",
      }),
      activo: !filtros.vencidos && !filtros.asignado && !filtros.prioridad,
    },
    {
      clave: "urgentes",
      etiqueta: "Urgentes",
      valor: resumen.urgentes,
      href: hrefTickets(filtros, {
        pagina: 1,
        prioridad: "urgente",
        vencidos: false,
        asignado: "",
      }),
      activo: filtros.prioridad === "urgente",
    },
    ...(resumen.vencidos !== undefined
      ? [
          {
            clave: "vencidos",
            etiqueta: "Vencidos",
            valor: resumen.vencidos,
            href: hrefTickets(filtros, {
              pagina: 1,
              vencidos: true,
              prioridad: "",
              asignado: "",
            }),
            activo: filtros.vencidos,
          },
        ]
      : []),
    ...(resumen.sin_asignar !== undefined
      ? [
          {
            clave: "sin_asignar",
            etiqueta: "Sin asignar",
            valor: resumen.sin_asignar,
            href: hrefTickets(filtros, {
              pagina: 1,
              asignado: "ninguno",
              vencidos: false,
              prioridad: "",
            }),
            activo: filtros.asignado === "ninguno",
          },
        ]
      : []),
  ];

  return (
    <div className={styles.pagina}>
      <Encabezado />

      <Chips etiqueta="Atajos de la bandeja">
        {chips.map((c) => (
          <Chip key={c.clave} href={c.href} activo={c.activo} hay={c.valor > 0 && c.clave !== "abiertos"}>
            {c.etiqueta} <span className="cifra">{c.valor}</span>
          </Chip>
        ))}
      </Chips>

      {bandeja.casos.length > 0 ? (
        <Form
          action="/tickets"
          className={styles.filtros}
          aria-label="Filtrar tickets"
          key={JSON.stringify({ ...filtros, pagina: 1 })}
        >
          <div className={styles.campoFiltro}>
            <label htmlFor="t-q">Código o asunto</label>
            <input
              id="t-q"
              name="q"
              type="search"
              defaultValue={filtros.q}
              autoComplete="off"
            />
          </div>
          <div className={styles.campoFiltro}>
            <label htmlFor="t-estado">Estado</label>
            <select id="t-estado" name="estado" defaultValue={filtros.estado}>
              <option value="">Todos</option>
              {ESTADOS_TICKET.map((e) => (
                <option key={e} value={e}>
                  {ETIQUETA_ESTADO_TICKET[e]}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.campoFiltro}>
            <label htmlFor="t-categoria">Categoría</label>
            <select
              id="t-categoria"
              name="categoria"
              defaultValue={filtros.categoria}
            >
              <option value="">Todas</option>
              {CATEGORIAS.map((c) => (
                <option key={c} value={c}>
                  {ETIQUETA_CATEGORIA_CASO[c]}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.campoFiltro}>
            <label htmlFor="t-prioridad">Prioridad</label>
            <select
              id="t-prioridad"
              name="prioridad"
              defaultValue={filtros.prioridad}
            >
              <option value="">Todas</option>
              {PRIORIDADES.map((p) => (
                <option key={p} value={p}>
                  {ETIQUETA_PRIORIDAD[p]}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.campoFiltro}>
            <label htmlFor="t-asignado">Dueño</label>
            <select
              id="t-asignado"
              name="asignado"
              defaultValue={filtros.asignado}
            >
              <option value="">Cualquiera</option>
              <option value="ninguno">Sin asignar</option>
              <option value="mios">Míos</option>
            </select>
          </div>
          <label className={styles.casillaVencidos}>
            <input
              type="checkbox"
              name="vencidos"
              value="1"
              defaultChecked={filtros.vencidos}
            />
            Solo vencidos
          </label>
          <button type="submit" className={styles.filtrar}>
            Filtrar
          </button>
          <Link href="/tickets" className={styles.limpiar}>
            Limpiar
          </Link>
        </Form>
      ) : null}

      {bandeja.casos.length > 0 && hayFiltrosTickets(filtros) ? (
        <p className={styles.tenue} aria-live="polite">
          Mostrando {casos.length} de {bandeja.casos.length} tickets.
        </p>
      ) : null}

      {ordenados.length === 0 ? (
        <EstadoVacio titulo={bandeja.casos.length === 0 ? "No hay casos abiertos" : "Ningún ticket cumple esos filtros"}>
          {bandeja.casos.length === 0 ? (
            "Un caso aparece cuando el flujo falla (pago, stock, lectura de lista) o cuando un acudiente abre una PQRS."
          ) : (
            <Link href="/tickets">Ver todos</Link>
          )}
        </EstadoVacio>
      ) : (
        <>
          <ul className={styles.rejilla}>
            {pagina.items.map((caso) => (
              <TarjetaTicket
                key={caso.caso_id}
                caso={caso}
                ahora={ahora}
                yo={yo}
              />
            ))}
          </ul>
          {pagina.paginas > 1 ? (
            <nav className={styles.paginacion} aria-label="Páginas de tickets">
              {pagina.pagina > 1 ? (
                <Link
                  href={hrefTickets(filtros, { pagina: pagina.pagina - 1 })}
                  rel="prev"
                >
                  ← Anterior
                </Link>
              ) : (
                <span className={styles.tenue}>← Anterior</span>
              )}
              <span>
                Página {pagina.pagina} de {pagina.paginas} · {pagina.total}{" "}
                tickets
              </span>
              {pagina.pagina < pagina.paginas ? (
                <Link
                  href={hrefTickets(filtros, { pagina: pagina.pagina + 1 })}
                  rel="next"
                >
                  Siguiente →
                </Link>
              ) : (
                <span className={styles.tenue}>Siguiente →</span>
              )}
            </nav>
          ) : null}
        </>
      )}
    </div>
  );
}
