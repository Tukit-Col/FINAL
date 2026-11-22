import { notFound, redirect } from "next/navigation";
import type { Trabajo } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
import { entregaParaReintento, type EntregaPrevia } from "@/lib/pagar-pedido";
import { matriculasDeLaSesion, pedidosDeLaSesion, sesionActual, tokenDeSesion } from "@/lib/sesion";
import VistaKits from "./VistaKits";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Tus tres kits — Tukit",
};

async function entregaPrevia(trabajoId: string): Promise<EntregaPrevia | null> {
  try {
    return entregaParaReintento(await pedidosDeLaSesion(), trabajoId, Date.now());
  } catch {
    return null;
  }
}

export default async function PaginaKits({
  params,
  searchParams,
}: {
  params: Promise<{ trabajo_id: string }>;
  searchParams: Promise<{ pagar?: string }>;
}) {
  const { trabajo_id } = await params;
  return conAvisoDeLimite(() => kits(trabajo_id, searchParams));
}

async function kits(trabajo_id: string, searchParams: Promise<{ pagar?: string }>) {
  let trabajo: Trabajo;
  try {
    trabajo = await origenDeDatos().consultarTrabajo(trabajo_id, await tokenDeSesion());
  } catch (causa) {
    if (causa instanceof ErrorTukit) {
      if (causa.estado === 401) {
        redirect(`/ingresar?destino=${encodeURIComponent(`/kits/${trabajo_id}`)}`);
      }
      if (causa.estado === 404) notFound();
    }
    throw causa;
  }

  if (trabajo.estado !== "publicado") {
    redirect(`/esperando/${trabajo_id}`);
  }

  const [sesion, matriculas, entrega, consulta] = await Promise.all([
    sesionActual(),
    matriculasDeLaSesion(),
    entregaPrevia(trabajo_id),
    searchParams,
  ]);

  return (
      <VistaKits
        trabajo={trabajo}
        correo={sesion?.correo ?? ""}
        matriculas={matriculas.map(({ colegio_id, grado, apodo }) => ({ colegio_id, grado, apodo }))}
        entregaPrevia={entrega}
        abrirPago={consulta.pagar === "1"}
      />
  );
}
