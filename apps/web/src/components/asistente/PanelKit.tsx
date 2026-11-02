"use client";

// El panel «Pidenos un cambio» de /kits. El modelo solo propone; un cambio se
// aplica unicamente cuando el acudiente lo confirma, y por la ruta de siempre
// (`PUT /api/trabajos/{id}/kits/{perfil}/lineas/{item}/producto`).

import { useState } from "react";
import { useRouter } from "next/navigation";
import { validarEspec, type Componente } from "./espec";
import { ExplicacionKit, PropuestaCambio, PropuestaDescarte } from "./Componentes";
import estilos from "./Asistente.module.css";

const PERFILES = ["Ahorrador", "Fan", "A tu Medida", "Premium"] as const;
type Perfil = (typeof PERFILES)[number];
type Estado = "pendiente" | "aplicada" | "rechazada";

const EJEMPLOS = ["Más barato en cuadernos", "¿Por qué este kit cuesta eso?", "Quita lo que no necesito"];

async function avisarDecision(propuesta_id: string, decision: "aceptada" | "rechazada", tipo: "cambio" | "descarte") {
  try {
    await fetch("/api/asistente/decision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ propuesta_id, decision, tipo }),
    });
  } catch {
    /* la bitacora no estorba */
  }
}

export default function PanelKit({ trabajoId }: { trabajoId: string }) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [perfil, setPerfil] = useState<Perfil>("Ahorrador");
  const [texto, setTexto] = useState("");
  const [cargando, setCargando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [retirado, setRetirado] = useState(false);
  const [propuestaId, setPropuestaId] = useState<string | null>(null);
  const [componentes, setComponentes] = useState<Componente[]>([]);
  const [estados, setEstados] = useState<Record<number, Estado>>({});
  const [ocupado, setOcupado] = useState(false);

  if (retirado) return null;

  async function proponer() {
    if (!texto.trim() || cargando) return;
    setCargando(true);
    setAviso(null);
    setComponentes([]);
    setEstados({});
    try {
      const respuesta = await fetch(`/api/asistente/kits/${encodeURIComponent(trabajoId)}/proponer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto, perfil }),
      });
      const cuerpo = (await respuesta.json().catch(() => null)) as Record<string, unknown> | null;
      if (respuesta.status === 503) {
        setRetirado(true);
        return;
      }
      if (!respuesta.ok || !cuerpo) {
        setAviso(
          respuesta.status === 404
            ? "No encontramos ese kit en tu cuenta. Entra con tu cuenta para pedir cambios."
            : "No pudimos leer eso. Prueba de nuevo.",
        );
        return;
      }
      if (cuerpo["estado"] !== "propuesta") {
        setAviso(typeof cuerpo["mensaje"] === "string" ? cuerpo["mensaje"] : "No encontramos un cambio con eso.");
        return;
      }
      const ui = validarEspec(cuerpo["ui"]);
      if (!ui) {
        setRetirado(true);
        return;
      }
      setPropuestaId(String(cuerpo["propuesta_id"]));
      setComponentes(ui.componentes);
    } catch {
      setRetirado(true);
    } finally {
      setCargando(false);
    }
  }

  async function aceptar(indice: number, c: Extract<Componente, { tipo: "PropuestaCambio" }>) {
    setOcupado(true);
    try {
      const url =
        `/api/trabajos/${encodeURIComponent(c.props.trabajo_id)}/kits/${encodeURIComponent(c.props.perfil)}` +
        `/lineas/${encodeURIComponent(c.props.item_id)}/producto`;
      const respuesta = await fetch(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku: c.props.despues.sku }),
      });
      if (!respuesta.ok) {
        setAviso("No pudimos hacer ese cambio. Puedes hacerlo a mano en el renglón del kit.");
        return;
      }
      setEstados((e) => ({ ...e, [indice]: "aplicada" }));
      if (propuestaId) void avisarDecision(propuestaId, "aceptada", "cambio");
      router.refresh();
    } catch {
      setAviso("No pudimos hacer ese cambio. Puedes hacerlo a mano en el renglón del kit.");
    } finally {
      setOcupado(false);
    }
  }

  function rechazar(indice: number) {
    setEstados((e) => ({ ...e, [indice]: "rechazada" }));
    if (propuestaId) void avisarDecision(propuestaId, "rechazada", "cambio");
  }

  return (
    <section className={estilos.panel} aria-labelledby="asistente-kit-titulo">
      <h2 id="asistente-kit-titulo" className={estilos.titulo}>
        Pídenos un cambio
      </h2>
      {!abierto ? (
        <div className={estilos.acciones}>
          <button type="button" className={estilos.secundario} onClick={() => setAbierto(true)}>
            Contarle a la asistente qué quieres cambiar
          </button>
        </div>
      ) : (
        <>
          <p className={estilos.ayuda}>Te proponemos el cambio y tú decides. No tocamos nada sin tu sí.</p>
          <label className={estilos.rotulo} htmlFor="asistente-perfil">
            Kit
          </label>
          <select
            id="asistente-perfil"
            className={estilos.entrada}
            style={{ minHeight: 48 }}
            value={perfil}
            onChange={(e) => setPerfil(e.target.value as Perfil)}
          >
            {PERFILES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <label className={estilos.rotulo} htmlFor="asistente-kit-texto">
            Qué quieres cambiar
          </label>
          <textarea
            id="asistente-kit-texto"
            className={estilos.entrada}
            value={texto}
            maxLength={1000}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Más barato en cuadernos"
          />
          <div className={estilos.ejemplos}>
            {EJEMPLOS.map((e) => (
              <button key={e} type="button" className={estilos.ejemplo} onClick={() => setTexto(e)}>
                {e}
              </button>
            ))}
          </div>
          <div className={estilos.acciones}>
            <button type="button" className={estilos.primario} onClick={proponer} disabled={cargando || !texto.trim()}>
              {cargando ? "Pensando…" : "Proponer cambio"}
            </button>
          </div>
          <div aria-live="polite">{aviso && <p className={estilos.aviso}>{aviso}</p>}</div>
          {componentes.length > 0 && (
            <ul className={estilos.lista}>
              {componentes.map((c, i) => {
                if (c.tipo === "PropuestaCambio") {
                  return (
                    <PropuestaCambio
                      key={i}
                      {...c.props}
                      estado={estados[i] ?? "pendiente"}
                      ocupado={ocupado || !c.props.aplicable}
                      onAceptar={() => void aceptar(i, c)}
                      onRechazar={() => rechazar(i)}
                    />
                  );
                }
                if (c.tipo === "PropuestaDescarte") return <PropuestaDescarte key={i} {...c.props} />;
                if (c.tipo === "ExplicacionKit") return <ExplicacionKit key={i} {...c.props} />;
                return null;
              })}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
