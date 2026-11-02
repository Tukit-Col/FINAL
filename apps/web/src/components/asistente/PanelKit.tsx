"use client";

// El asistente de /kits: un chat flotante en la esquina. El modelo solo
// propone; un cambio se aplica unicamente cuando el acudiente lo confirma, y
// por la ruta de siempre (`PUT /api/trabajos/{id}/kits/{perfil}/lineas/{item}/producto`).
// El kit sobre el que se habla es el que el acudiente esta mirando.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageCircle, Send, X } from "lucide-react";
import { validarEspec, type Componente } from "./espec";
import { aplicacionDePropuesta, type PropuestaAplicable } from "./aplicar";
import { ExplicacionKit, PropuestaCambio, PropuestaDescarte } from "./Componentes";
import estilos from "./Asistente.module.css";

type Estado = "pendiente" | "aplicada" | "rechazada";

type Respuesta =
  | { tipo: "pensando" }
  | { tipo: "texto"; texto: string }
  | { tipo: "propuesta"; propuestaId: string; componentes: Componente[] };

interface Turno {
  pregunta: string;
  respuesta: Respuesta;
}

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

export default function PanelKit({ trabajoId, perfil }: { trabajoId: string; perfil: string }) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [estados, setEstados] = useState<Record<string, Estado>>({});
  const [ocupado, setOcupado] = useState(false);
  const [retirado, setRetirado] = useState(false);
  const entrada = useRef<HTMLTextAreaElement>(null);
  const fondo = useRef<HTMLDivElement>(null);

  const cargando = turnos.at(-1)?.respuesta.tipo === "pensando";

  useEffect(() => {
    if (abierto) entrada.current?.focus();
  }, [abierto]);

  useEffect(() => {
    fondo.current?.scrollIntoView({ block: "end" });
  }, [turnos]);

  useEffect(() => {
    if (!abierto) return;
    const alEscape = (e: KeyboardEvent) => e.key === "Escape" && setAbierto(false);
    window.addEventListener("keydown", alEscape);
    return () => window.removeEventListener("keydown", alEscape);
  }, [abierto]);

  if (retirado) return null;

  function responder(respuesta: Respuesta) {
    setTurnos((t) => [...t.slice(0, -1), { pregunta: t.at(-1)?.pregunta ?? "", respuesta }]);
  }

  async function proponer(pregunta: string) {
    if (!pregunta.trim() || cargando) return;
    setTexto("");
    setTurnos((t) => [...t, { pregunta, respuesta: { tipo: "pensando" } }]);
    try {
      const respuesta = await fetch(`/api/asistente/kits/${encodeURIComponent(trabajoId)}/proponer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: pregunta, perfil }),
      });
      const cuerpo = (await respuesta.json().catch(() => null)) as Record<string, unknown> | null;
      if (respuesta.status === 503) {
        setRetirado(true);
        return;
      }
      if (!respuesta.ok || !cuerpo) {
        responder({
          tipo: "texto",
          texto:
            respuesta.status === 404
              ? "No encontré ese kit en tu cuenta. Entra con tu cuenta para pedir cambios."
              : "No pude leer eso. ¿Lo intentas de nuevo con otras palabras?",
        });
        return;
      }
      if (cuerpo["estado"] !== "propuesta") {
        responder({
          tipo: "texto",
          texto: typeof cuerpo["mensaje"] === "string" ? cuerpo["mensaje"] : "No encontré un cambio con eso.",
        });
        return;
      }
      const ui = validarEspec(cuerpo["ui"]);
      if (!ui) {
        setRetirado(true);
        return;
      }
      responder({ tipo: "propuesta", propuestaId: String(cuerpo["propuesta_id"]), componentes: ui.componentes });
    } catch {
      setRetirado(true);
    }
  }

  // Lo aplica el padre, no el modelo: la misma llamada que hace el renglón del kit,
  // con su sesión; el servidor exige que el kit sea suyo.
  async function aceptar(clave: string, propuestaId: string, c: PropuestaAplicable) {
    const aplicacion = aplicacionDePropuesta(c);
    if (!aplicacion) return;
    setOcupado(true);
    try {
      const respuesta = await fetch(aplicacion.url, {
        method: aplicacion.metodo,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(aplicacion.cuerpo),
      });
      if (!respuesta.ok) {
        setTurnos((t) => [
          ...t,
          { pregunta: "", respuesta: { tipo: "texto", texto: "No pude hacer ese cambio. Puedes hacerlo a mano en el renglón del kit." } },
        ]);
        return;
      }
      setEstados((e) => ({ ...e, [clave]: "aplicada" }));
      void avisarDecision(propuestaId, "aceptada", aplicacion.tipo);
      router.refresh();
    } finally {
      setOcupado(false);
    }
  }

  function rechazar(clave: string, propuestaId: string, tipo: "cambio" | "descarte") {
    setEstados((e) => ({ ...e, [clave]: "rechazada" }));
    void avisarDecision(propuestaId, "rechazada", tipo);
  }

  if (!abierto) {
    return (
      <button type="button" className={estilos.burbuja} onClick={() => setAbierto(true)}>
        <MessageCircle size={22} aria-hidden="true" />
        <span>¿Cambiamos algo?</span>
      </button>
    );
  }

  return (
    <section className={estilos.ventana} role="dialog" aria-labelledby="asistente-kit-titulo">
      <header className={estilos.cabeceraChat}>
        <div>
          <h2 id="asistente-kit-titulo" className={estilos.titulo}>
            Asistente de tu kit
          </h2>
          <p className={estilos.ayuda}>Hablamos del kit {perfil}. Te propongo y tú decides.</p>
        </div>
        <button type="button" className={estilos.cerrar} onClick={() => setAbierto(false)} aria-label="Cerrar el asistente">
          <X size={20} aria-hidden="true" />
        </button>
      </header>

      <div className={estilos.mensajes} aria-live="polite">
        <p className={estilos.msgTukit}>
          Hola. Dime qué quieres cambiar del kit y te muestro la propuesta. No toco nada sin tu sí.
        </p>
        {turnos.length === 0 && (
          <div className={estilos.ejemplos}>
            {EJEMPLOS.map((e) => (
              <button key={e} type="button" className={estilos.ejemplo} onClick={() => void proponer(e)}>
                {e}
              </button>
            ))}
          </div>
        )}
        {turnos.map((turno, t) => (
          <div key={t} className={estilos.turno}>
            {turno.pregunta && <p className={estilos.msgPadre}>{turno.pregunta}</p>}
            {turno.respuesta.tipo === "pensando" && <p className={`${estilos.msgTukit} ${estilos.pensando}`}>Pensando…</p>}
            {turno.respuesta.tipo === "texto" && <p className={estilos.msgTukit}>{turno.respuesta.texto}</p>}
            {turno.respuesta.tipo === "propuesta" && (
              <ul className={estilos.lista}>
                {turno.respuesta.componentes.map((c, i) => {
                  const clave = `${t}-${i}`;
                  const propuestaId = (turno.respuesta as { propuestaId: string }).propuestaId;
                  if (c.tipo === "PropuestaCambio") {
                    return (
                      <PropuestaCambio
                        key={clave}
                        {...c.props}
                        estado={estados[clave] ?? "pendiente"}
                        ocupado={ocupado || !c.props.aplicable}
                        onAceptar={() => void aceptar(clave, propuestaId, c)}
                        onRechazar={() => rechazar(clave, propuestaId, "cambio")}
                      />
                    );
                  }
                  if (c.tipo === "PropuestaDescarte") {
                    return (
                      <PropuestaDescarte
                        key={clave}
                        {...c.props}
                        estado={estados[clave] ?? "pendiente"}
                        ocupado={ocupado || !c.props.aplicable}
                        onAceptar={() => void aceptar(clave, propuestaId, c)}
                        onRechazar={() => rechazar(clave, propuestaId, "descarte")}
                      />
                    );
                  }
                  if (c.tipo === "ExplicacionKit") return <ExplicacionKit key={clave} {...c.props} />;
                  return null;
                })}
              </ul>
            )}
          </div>
        ))}
        <div ref={fondo} />
      </div>

      <form
        className={estilos.redactar}
        onSubmit={(e) => {
          e.preventDefault();
          void proponer(texto);
        }}
      >
        <textarea
          id="asistente-kit-texto"
          aria-label="Qué quieres cambiar"
          ref={entrada}
          className={estilos.entradaChat}
          value={texto}
          rows={1}
          maxLength={1000}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void proponer(texto);
            }
          }}
          placeholder="Ej.: más barato en cuadernos"
        />
        <button type="submit" className={estilos.enviar} disabled={cargando || !texto.trim()} aria-label="Enviar">
          <Send size={18} aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}
