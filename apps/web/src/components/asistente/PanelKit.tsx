"use client";

// El asistente de /kits: un chat flotante en la esquina. El modelo solo
// propone; un cambio se aplica unicamente cuando el acudiente lo confirma, y
// por la ruta de siempre (`PUT /api/trabajos/{id}/kits/{perfil}/lineas/{item}/producto`).
// El kit sobre el que se habla es el que el acudiente esta mirando.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Minus, MessageCircle, RotateCcw, Send, X } from "lucide-react";
import { ejemplosSeguros, pedidoAnteriorSeguro, validarEspec, type Componente, type PedidoAnterior } from "./espec";
import { aplicacionDePropuesta, pendientesDelTurno, renglonesPorDecidir, type PropuestaAplicable } from "./aplicar";
import { iluminarRenglones, irARenglon } from "./resaltar";
import { ExplicacionKit, PropuestaCambio, PropuestaDescarte, ResumenLote } from "./Componentes";
import { sugerenciasDe, type UltimaRespuesta } from "./sugerencias";
import estilos from "./Asistente.module.css";

type Estado = "pendiente" | "aplicada" | "rechazada";

type Respuesta =
  | { tipo: "pensando" }
  | { tipo: "texto"; texto: string }
  | { tipo: "ayuda"; texto: string; ejemplos: string[] }
  | { tipo: "propuesta"; propuestaId: string; componentes: Componente[] };

interface Turno {
  pregunta: string;
  respuesta: Respuesta;
}

type Servicio = "revisando" | "activo" | "apagado" | "sin_modelo" | "caido";

const AVISO_SERVICIO: Record<Exclude<Servicio, "revisando" | "activo">, string> = {
  apagado: "El asistente no está activo en este entorno. Puedes ajustar cada renglón del kit a mano.",
  sin_modelo: "El asistente está encendido pero no tiene configurado el modelo en este entorno. Puedes ajustar el kit a mano.",
  caido: "No logro conectar con el asistente ahora. Puedes ajustar el kit a mano o volver a intentarlo en un momento.",
};


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
  const [servicio, setServicio] = useState<Servicio>("revisando");
  // El ultimo pedido por categoria, para que "y en colores tambien" se entienda en el turno
  // siguiente. Son dos palabras que devolvio el servidor, no lo que escribio el padre.
  const [anterior, setAnterior] = useState<PedidoAnterior | null>(null);
  const entrada = useRef<HTMLTextAreaElement>(null);
  const caja = useRef<HTMLDivElement>(null);
  const ultimoTurno = useRef<HTMLDivElement>(null);

  const cargando = turnos.at(-1)?.respuesta.tipo === "pensando";
  const ultimaTipo = turnos.at(-1)?.respuesta.tipo;
  const ultima: UltimaRespuesta =
    ultimaTipo === "propuesta" || ultimaTipo === "ayuda" || ultimaTipo === "texto" ? ultimaTipo : "ninguna";
  // Siempre hay sugerencias: se recalculan despues de cada respuesta, sin repetir las ya tocadas.
  const sugerencias = sugerenciasDe(
    ultima,
    anterior,
    turnos.slice(-2).map((t) => t.pregunta),
  );
  const sinServicio = servicio === "apagado" || servicio === "sin_modelo" || servicio === "caido";

  useEffect(() => {
    if (abierto) entrada.current?.focus();
  }, [abierto]);

  // Una sola consulta barata (sin modelo) al abrir: si el asistente no esta activo no se
  // ofrecen sugerencias que no van a funcionar.
  useEffect(() => {
    if (!abierto || servicio !== "revisando") return;
    let vigente = true;
    fetch("/api/asistente/estado", { cache: "no-store" })
      .then((r) => r.json() as Promise<{ estado?: unknown }>)
      .then((j) => {
        const e = j.estado;
        if (vigente) setServicio(e === "activo" || e === "apagado" || e === "sin_modelo" ? e : "caido");
      })
      .catch(() => vigente && setServicio("caido"));
    return () => {
      vigente = false;
    };
  }, [abierto, servicio]);

  // Mientras piensa, al fondo. Cuando llega una propuesta, el chat se queda en su comienzo
  // (el resumen y la primera tarjeta): con 4 cuadernos de una, el padre ve el lote entero
  // y su "Aceptar todos" en vez de aterrizar en la ultima tarjeta como si fueran sueltas.
  const respuestaFinal = turnos.at(-1)?.respuesta.tipo;
  useEffect(() => {
    // Solo se mueve la caja del chat: un scrollIntoView aqui cortaria el desplazamiento
    // de la pagina hacia el renglon.
    const c = caja.current;
    if (!c) return;
    const turno = ultimoTurno.current;
    c.scrollTop =
      respuestaFinal === "propuesta" && turno ? turno.offsetTop - 8 : c.scrollHeight;
  }, [turnos.length, respuestaFinal]);

  // Los renglones del kit que alguna propuesta abierta quiere tocar quedan iluminados en la
  // pagina, y al llegar una propuesta nueva la pagina va al primero de ellos.
  const porDecidir = renglonesPorDecidir(
    turnos.map((t) => (t.respuesta.tipo === "propuesta" ? t.respuesta.componentes : null)),
    estados,
  );
  const clavePorDecidir = porDecidir.join("|");
  useEffect(() => {
    if (!abierto) return;
    return iluminarRenglones(clavePorDecidir ? clavePorDecidir.split("|") : []);
  }, [abierto, clavePorDecidir]);

  const primeroDelUltimo = (() => {
    const ultima = turnos.at(-1)?.respuesta;
    if (ultima?.tipo !== "propuesta") return null;
    const c = ultima.componentes.find((x) => x.tipo === "PropuestaCambio" || x.tipo === "PropuestaDescarte");
    return c && "item_id" in c.props ? String(c.props.item_id) : null;
  })();
  useEffect(() => {
    if (primeroDelUltimo) irARenglon(primeroDelUltimo);
  }, [primeroDelUltimo, turnos.length]);

  useEffect(() => {
    if (!abierto) return;
    const alEscape = (e: KeyboardEvent) => e.key === "Escape" && cerrar();
    window.addEventListener("keydown", alEscape);
    return () => window.removeEventListener("keydown", alEscape);
  }, [abierto]);

  // Al cerrar, un "no conecta" se vuelve a revisar la proxima vez que se abra.
  function reiniciar() {
    setTurnos([]);
    setEstados({});
    setAnterior(null);
    setTexto("");
    entrada.current?.focus();
  }

  // Minimizar conserva la conversacion; cerrar la empieza de cero la proxima vez.
  function cerrar(reinicia = false) {
    if (reinicia) {
      setTurnos([]);
      setEstados({});
      setAnterior(null);
      setTexto("");
    }
    setAbierto(false);
    setServicio((v) => (v === "caido" ? "revisando" : v));
  }

  // Un fallo puntual (el modelo tardo o respondio algo ilegible): se puede reintentar.
  function noDisponible() {
    responder({
      tipo: "texto",
      texto: "No pude responder esta vez. Inténtalo de nuevo en un momento o ajusta el renglón del kit a mano.",
    });
  }

  // Apagado en el servidor (sin TUKIT_ASISTENTE): se dice tal cual, sin sugerir que "no puede".
  function apagado() {
    setServicio("apagado");
    responder({ tipo: "texto", texto: AVISO_SERVICIO.apagado });
  }

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
        body: JSON.stringify({ texto: pregunta, perfil, ...(anterior ? { anterior } : {}) }),
      });
      const cuerpo = (await respuesta.json().catch(() => null)) as Record<string, unknown> | null;
      if (respuesta.status === 503) {
        if (cuerpo?.["error"] === "asistente_desactivado") apagado();
        else noDisponible();
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
      if (cuerpo["estado"] === "ayuda") {
        responder({
          tipo: "ayuda",
          texto: typeof cuerpo["mensaje"] === "string" ? cuerpo["mensaje"] : "Puedo ajustar el kit.",
          ejemplos: ejemplosSeguros(cuerpo["ejemplos"]),
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
        noDisponible();
        return;
      }
      const contexto = pedidoAnteriorSeguro(cuerpo["contexto"]);
      if (contexto) setAnterior(contexto);
      responder({ tipo: "propuesta", propuestaId: String(cuerpo["propuesta_id"]), componentes: ui.componentes });
    } catch {
      noDisponible();
    }
  }

  // Lo aplica el padre, no el modelo: la misma llamada que hace el renglon del kit,
  // con su sesion; el servidor exige que el kit sea suyo. Devuelve si el servidor lo acepto.
  async function aplicarUna(clave: string, propuestaId: string, c: PropuestaAplicable): Promise<boolean> {
    const aplicacion = aplicacionDePropuesta(c);
    if (!aplicacion) return false;
    const respuesta = await fetch(aplicacion.url, {
      method: aplicacion.metodo,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(aplicacion.cuerpo),
    });
    if (!respuesta.ok) return false;
    setEstados((e) => ({ ...e, [clave]: "aplicada" }));
    void avisarDecision(propuestaId, "aceptada", aplicacion.tipo);
    return true;
  }

  function avisarFallo() {
    setTurnos((t) => [
      ...t,
      { pregunta: "", respuesta: { tipo: "texto", texto: "No pude hacer ese cambio. Puedes hacerlo a mano en el renglón del kit." } },
    ]);
  }

  async function aceptar(clave: string, propuestaId: string, c: PropuestaAplicable) {
    setOcupado(true);
    try {
      if (await aplicarUna(clave, propuestaId, c)) router.refresh();
      else avisarFallo();
    } finally {
      setOcupado(false);
    }
  }

  // "Aceptar todos": una llamada PUT por propuesta, una tras otra y con la sesion del padre.
  // Si una falla se detiene ahi y lo ya aplicado queda aplicado; no existe escritura en lote.
  async function aceptarTodos(turno: number, propuestaId: string, componentes: Componente[]) {
    setOcupado(true);
    let fallo = false;
    try {
      for (const { clave, componente } of pendientesDelTurno(componentes, turno, estados)) {
        if (!(await aplicarUna(clave, propuestaId, componente))) {
          fallo = true;
          break;
        }
      }
      router.refresh();
      if (fallo) avisarFallo();
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
        <span>Pregúntale a Tukit</span>
      </button>
    );
  }

  const activo = servicio === "activo";
  const estadoTexto = servicio === "revisando" ? "Conectando…" : activo ? "Activo" : "Inactivo";

  return (
    <section className={estilos.ventana} role="dialog" aria-modal="false" aria-labelledby="asistente-kit-titulo">
      <header className={estilos.cabeceraChat}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className={estilos.avatar} src="/marca/icon-192.png" alt="" width={40} height={40} />
        <div className={estilos.cabeceraTexto}>
          <h2 id="asistente-kit-titulo" className={estilos.titulo}>
            Asistente de tu kit
          </h2>
          <p className={estilos.estadoLinea}>
            <span className={`${estilos.punto} ${activo ? estilos.puntoActivo : ""}`} aria-hidden="true" />
            {estadoTexto}
          </p>
        </div>
        <div className={estilos.acciones}>
          <button type="button" className={estilos.cerrar} onClick={reiniciar} aria-label="Reiniciar la conversación" title="Reiniciar">
            <RotateCcw size={18} aria-hidden="true" />
          </button>
          <button type="button" className={estilos.cerrar} onClick={() => cerrar()} aria-label="Minimizar el asistente" title="Minimizar">
            <Minus size={18} aria-hidden="true" />
          </button>
          <button type="button" className={estilos.cerrar} onClick={() => cerrar(true)} aria-label="Cerrar el asistente" title="Cerrar">
            <X size={18} aria-hidden="true" />
          </button>
        </div>
      </header>
      <p className={estilos.alcance}>
        Hablamos del kit <strong>{perfil}</strong>. Te propongo y tú decides.
      </p>

      <div ref={caja} className={estilos.mensajes} role="log" aria-live="polite" aria-label="Conversación con Tukit" tabIndex={0}>
        <p className={estilos.msgTukit}>
          Hola, soy Tukit. Dime qué quieres cambiar del kit y te muestro la propuesta. No toco nada sin tu sí.
        </p>
        {servicio !== "revisando" && servicio !== "activo" && (
          <p className={estilos.msgTukit} role="status">
            {AVISO_SERVICIO[servicio]}
          </p>
        )}
        {turnos.map((turno, t) => (
          <div key={t} className={estilos.turno} ref={t === turnos.length - 1 ? ultimoTurno : undefined}>
            {turno.pregunta && <p className={estilos.msgPadre}>{turno.pregunta}</p>}
            {turno.respuesta.tipo === "pensando" && <p className={`${estilos.msgTukit} ${estilos.pensando}`} aria-label="Tukit está escribiendo"><span className={estilos.punto3} /><span className={estilos.punto3} /><span className={estilos.punto3} /></p>}
            {turno.respuesta.tipo === "texto" && <p className={estilos.msgTukit}>{turno.respuesta.texto}</p>}
            {turno.respuesta.tipo === "ayuda" && (
              <p className={estilos.msgTukit}>{turno.respuesta.texto}</p>
            )}
            {turno.respuesta.tipo === "propuesta" && (
              <ul className={estilos.lista}>
                {turno.respuesta.componentes.map((c, i) => {
                  const clave = `${t}-${i}`;
                  const propuestaId = (turno.respuesta as { propuestaId: string }).propuestaId;
                  const todas = (turno.respuesta as { componentes: Componente[] }).componentes;
                  if (c.tipo === "ResumenLote") {
                    return (
                      <ResumenLote
                        key={clave}
                        {...c.props}
                        pendientes={pendientesDelTurno(todas, t, estados).length}
                        ocupado={ocupado}
                        onAceptarTodos={() => void aceptarTodos(t, propuestaId, todas)}
                      />
                    );
                  }
                  if (c.tipo === "PropuestaCambio") {
                    return (
                      <PropuestaCambio
                        key={clave}
                        {...c.props}
                        estado={estados[clave] ?? "pendiente"}
                        ocupado={ocupado || !c.props.aplicable}
                        onAceptar={() => void aceptar(clave, propuestaId, c)}
                        onRechazar={() => rechazar(clave, propuestaId, "cambio")}
                        onVer={() => irARenglon(c.props.item_id)}
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
                        onVer={() => irARenglon(c.props.item_id)}
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
      </div>

      <div className={estilos.sugerencias} role="group" aria-label="Sugerencias">
        {sugerencias.map((e) => (
          <button key={e} type="button" className={estilos.ejemplo} disabled={cargando || sinServicio} onClick={() => void proponer(e)}>
            {e}
          </button>
        ))}
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
          disabled={sinServicio}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void proponer(texto);
            }
          }}
          placeholder="Ej.: más barato en los cuadernos"
        />
        <button type="submit" className={estilos.enviar} disabled={cargando || sinServicio || !texto.trim()} aria-label={cargando ? "Esperando respuesta" : "Enviar"} aria-busy={cargando}>
          <Send size={18} aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}
