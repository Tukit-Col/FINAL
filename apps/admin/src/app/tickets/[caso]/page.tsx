// `/tickets/[caso]` — un ticket con su conversacion.
//
// Muestra el cuerpo de la PQRS, la historia (respuestas del equipo, cambios de
// estado, vinculos) y deja responder al acudiente, mover el estado y ligar el
// ticket a un pedido. Solo staff: operacion responde 401/403 a cualquier otro y
// aqui eso se vuelve el mismo aviso de la bandeja. El correo del acudiente sale
// enmascarado del padron de identidad; el contacto nunca se guardo en operacion.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { CasoDetalleAdmin, EstadoCaso, Prioridad } from "@tukit/contrato";
import { ETIQUETA_CATEGORIA_CASO, ETIQUETA_PRIORIDAD } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos, urlWeb } from "@tukit/contrato/servidor";
import AccionesTicket from "@/components/AccionesTicket";
import AvisoAcceso from "@/components/AvisoAcceso";
import { formatearFecha } from "@/lib/formato";
import { motivoDeFallo } from "@/lib/logistica";
import { enmascararCorreo } from "@/lib/pedido-admin";
import { quienSoy, tokenDeSesion } from "@/lib/sesion";
import { ETIQUETA_ESTADO_TICKET } from "@/lib/tickets";
import styles from "./Ticket.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ caso: string }>;
}

function Migas() {
  return (
    <nav className={styles.migas}>
      <Link href="/tickets">← Tickets</Link>
    </nav>
  );
}

/** El correo del titular, del padron de identidad. Es un adorno: si identidad no
 *  responde, el ticket se muestra con el id de la cuenta. */
async function correoDelTitular(token: string, usuarioId: string | null): Promise<string | null> {
  if (!usuarioId) return null;
  try {
    const [acudiente] = await origenDeDatos().acudientesAdmin(token, [usuarioId]);
    return acudiente?.correo ?? null;
  } catch {
    return null;
  }
}

async function nombresDeActores(caso: CasoDetalleAdmin, token: string): Promise<Record<string, string>> {
  // Los actores y los dueños de las asignaciones (`datos.desde/hacia` son ids de usuario).
  const referidos = caso.eventos.flatMap((e) =>
    e.tipo === "asignacion" ? [e.datos["desde"], e.datos["hacia"]] : [],
  );
  const ids = [
    ...new Set(
      [...caso.eventos.map((e) => e.actor_id), caso.asignado_a, ...referidos].filter(
        (x): x is string => typeof x === "string" && x !== "",
      ),
    ),
  ];
  if (ids.length === 0) return {};
  try {
    return await origenDeDatos().nombresDeUsuarios(ids, token);
  } catch {
    return {};
  }
}

function etiquetaPrioridad(valor: unknown): string {
  return ETIQUETA_PRIORIDAD[valor as Prioridad] ?? String(valor);
}

function etiquetaEstado(valor: unknown): string {
  return ETIQUETA_ESTADO_TICKET[valor as EstadoCaso] ?? String(valor);
}

export default async function DetalleTicket({ params }: Props) {
  const { caso: casoId } = await params;
  const token = await tokenDeSesion();
  if (!token) {
    return (
      <div className={styles.pagina}>
        <Migas />
        <AvisoAcceso motivo="sin_sesion" />
      </div>
    );
  }

  let caso: CasoDetalleAdmin;
  try {
    caso = await origenDeDatos().casoAdmin(token, casoId);
  } catch (causa) {
    if (!(causa instanceof ErrorTukit)) throw causa;
    if (causa.estado === 404 || causa.estado === 400 || causa.estado === 422) notFound();
    return (
      <div className={styles.pagina}>
        <Migas />
        <AvisoAcceso motivo={motivoDeFallo(causa.estado)} />
      </div>
    );
  }

  const [correo, nombres, sesion] = await Promise.all([
    correoDelTitular(token, caso.usuario_id),
    nombresDeActores(caso, token),
    quienSoy(),
  ]);
  const quien = (id: string | null) => (id ? (nombres[id] ?? id.slice(0, 8)) : "Sistema");

  return (
    <div className={styles.pagina}>
      <Migas />

      <section className={styles.encabezado}>
        <h1>{caso.asunto}</h1>
        <div className={styles.hechos}>
          <span className={`${styles.estado} ${styles[`estado_${caso.estado}`]}`}>
            {ETIQUETA_ESTADO_TICKET[caso.estado]}
          </span>
          <span>{ETIQUETA_CATEGORIA_CASO[caso.categoria]}</span>
          <span>Prioridad {ETIQUETA_PRIORIDAD[caso.prioridad].toLowerCase()}</span>
          <span>
            {caso.asignado_a === null
              ? "Sin asignar"
              : caso.asignado_a === sesion?.usuarioId
                ? "Asignado a ti"
                : `Asignado a ${quien(caso.asignado_a)}`}
          </span>
          <span>Abierto {formatearFecha(caso.abierto_en)}</span>
          {caso.vence_en ? <span>Vence {formatearFecha(caso.vence_en)}</span> : null}
          {caso.resuelto_en ? <span>Resuelto {formatearFecha(caso.resuelto_en)}</span> : null}
        </div>
        <dl className={styles.datos}>
          <dt>Acudiente</dt>
          <dd>
            {caso.usuario_id
              ? correo
                ? enmascararCorreo(correo)
                : `cuenta ${caso.usuario_id.slice(0, 8)}`
              : "Sin titular (identidad no respondió al abrirlo)"}
          </dd>
          <dt>Pedido</dt>
          <dd>
            {caso.pedido_id ? (
              <Link href={`/logistica/${caso.pedido_id}`}>
                <code>{caso.pedido_id.slice(0, 8).toUpperCase()}</code> · ver pedido
              </Link>
            ) : (
              "Sin pedido vinculado"
            )}
          </dd>
          {caso.trabajo_id ? (
            <>
              <dt>Trabajo</dt>
              <dd>
                <Link href={`/trabajos/${caso.trabajo_id}`}>
                  <code>{caso.trabajo_id.slice(0, 8)}</code> · ver trabajo
                </Link>
              </dd>
            </>
          ) : null}
        </dl>
      </section>

      <section className={styles.bloque} aria-labelledby="conversacion-titulo">
        <h2 id="conversacion-titulo">Conversación</h2>
        <ol className={styles.conversacion}>
          <li className={styles.mensajeAcudiente}>
            <div className={styles.quien}>Acudiente · {formatearFecha(caso.abierto_en)}</div>
            <p>{caso.descripcion || "Sin descripción."}</p>
          </li>
          {caso.eventos.map((e, i) => {
            // Lo que el acudiente agrego desde su panel (/dashboard, mis casos).
            if (e.tipo === "comentario_acudiente") {
              return (
                <li key={i} className={styles.mensajeAcudiente}>
                  <div className={styles.quien}>Acudiente · {formatearFecha(e.creado_en)}</div>
                  <p>{String(e.datos["texto"] ?? "")}</p>
                </li>
              );
            }
            if (e.tipo === "respuesta") {
              return (
                <li key={i} className={styles.mensajeEquipo}>
                  <div className={styles.quien}>
                    {quien(e.actor_id)} · {formatearFecha(e.creado_en)}
                  </div>
                  <p>{String(e.datos["texto"] ?? "")}</p>
                </li>
              );
            }
            if (e.tipo === "nota_interna") {
              return (
                <li key={i} className={styles.mensajeNota}>
                  <div className={styles.quien}>
                    Nota interna · solo el equipo · {quien(e.actor_id)} · {formatearFecha(e.creado_en)}
                  </div>
                  <p>{String(e.datos["texto"] ?? "")}</p>
                </li>
              );
            }
            const texto =
              e.tipo === "asignacion"
                ? e.datos["hacia"]
                  ? `Asignado a ${quien(String(e.datos["hacia"]))}`
                  : "Ticket liberado (sin asignar)"
                : e.tipo === "prioridad"
                  ? `Prioridad: ${etiquetaPrioridad(e.datos["desde"])} → ${etiquetaPrioridad(e.datos["hacia"])}`
                  : e.tipo === "estado"
                ? `Estado: ${etiquetaEstado(e.datos["desde"])} → ${etiquetaEstado(e.datos["hacia"])}`
                : e.tipo === "pedido"
                  ? `Vinculado al pedido ${String(e.datos["pedido_id"] ?? "").slice(0, 8).toUpperCase()}`
                  : e.tipo;
            return (
              <li key={i} className={styles.evento}>
                {texto} · {quien(e.actor_id)} · {formatearFecha(e.creado_en)}
              </li>
            );
          })}
        </ol>
      </section>

      <AccionesTicket
        casoId={caso.caso_id}
        estado={caso.estado}
        pedidoId={caso.pedido_id}
        puedeAvisar={caso.usuario_id !== null}
        prioridad={caso.prioridad}
        asignadoA={caso.asignado_a}
        yo={sesion?.usuarioId ?? null}
        esAdmin={sesion?.esAdmin ?? false}
        urlIngresar={`${urlWeb()}/ingresar`}
      />
    </div>
  );
}
