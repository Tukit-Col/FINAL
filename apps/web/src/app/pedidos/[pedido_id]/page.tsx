// `/pedidos/[pedido_id]` — la pagina de UN pedido del acudiente: primero su
// linea de tiempo (en que paso va, desde cuando y si algo se desvio), luego los
// productos, el pago y la entrega.
//
// Server Component: el token sale de la cookie httponly y viaja a Comercio
// (`GET /v1/comercio/mis-pedidos/{id}`), que saca al acudiente de la sesion. Un
// pedido ajeno responde 404 igual que uno que no existe: aqui los dos son el
// mismo not-found, para no confirmar que el id existe. La linea de tiempo llega
// hecha de Comercio; esta pagina la pinta y no recalcula ninguna regla.

import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { ETIQUETA_ESTADO_PEDIDO, type PedidoDelAcudiente } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import EntregaPedido from "@/components/pedido/EntregaPedido";
import { MEDIOS_PAGO } from "@/components/pedido/medios";
import ResumenPedido from "@/components/pedido/ResumenPedido";
import { fechaHoraBogota } from "@/lib/pedido-vista";
import { tokenDeSesion } from "@/lib/sesion";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
import LineaDeTiempoPedido from "./LineaDeTiempoPedido";
import styles from "./PaginaPedido.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Tu pedido — Tukit" };

export default async function PaginaPedido({ params }: { params: Promise<{ pedido_id: string }> }) {
  const { pedido_id } = await params;
  // Un 429 (cupo agotado) pinta el aviso con la espera, no un error.
  return conAvisoDeLimite(() => paginaPedido(pedido_id));
}

async function paginaPedido(pedido_id: string) {
  const destino = `/ingresar?destino=${encodeURIComponent(`/pedidos/${pedido_id}`)}`;
  const token = await tokenDeSesion();
  if (!token) redirect(destino);

  let pedido: PedidoDelAcudiente;
  try {
    pedido = await origenDeDatos().miPedido(token, pedido_id);
  } catch (causa) {
    if (causa instanceof ErrorTukit) {
      // La sesion vencio: a ingresar y de vuelta aqui.
      if (causa.estado === 401) redirect(destino);
      // Ajeno, inexistente o un id que ni es un UUID: el mismo not-found.
      if ([400, 404, 422].includes(causa.estado)) notFound();
    }
    throw causa;
  }

  const medio = pedido.pago ? MEDIOS_PAGO[pedido.pago.metodo] : null;

  return (
    <div className={styles.pagina}>
      <div className={styles.contenedor}>
        <Link href="/dashboard#pedidos" className={styles.volver}>
          <ArrowLeft size={16} aria-hidden /> Mis pedidos
        </Link>

        <header className={styles.cabecera}>
          <h1 className={styles.titulo}>
            Pedido <span className={styles.codigo}>{pedido.pedido_id.slice(0, 8).toUpperCase()}</span>
          </h1>
          <p className={styles.resumen}>
            {ETIQUETA_ESTADO_PEDIDO[pedido.estado]} · Creado el{" "}
            <time dateTime={pedido.creado_en}>{fechaHoraBogota(pedido.creado_en)}</time>
          </p>
        </header>

        <LineaDeTiempoPedido
          linea={pedido.linea_de_tiempo}
          pedidoId={pedido.pedido_id}
          trabajoId={pedido.trabajo_id}
        />

        <ResumenPedido pedido={pedido} />

        <section className={styles.tarjeta} aria-labelledby="pago-titulo">
          <h2 id="pago-titulo" className={styles.subtitulo}>
            Pago
          </h2>
          {medio ? (
            <p className={styles.medio}>
              <medio.Icono size={18} aria-hidden /> {medio.nombre}
            </p>
          ) : (
            <p className={styles.tenue}>Todavía no hay un intento de pago.</p>
          )}
        </section>

        {pedido.envio && <EntregaPedido envio={pedido.envio} />}
      </div>
    </div>
  );
}
