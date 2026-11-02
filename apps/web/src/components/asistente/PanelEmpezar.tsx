"use client";

// El chat de /empezar: el acudiente cuenta que necesita, el asistente propone
// restricciones y el acudiente las edita y confirma. Confirmar NO envia nada al
// backend de pedidos: publica la propuesta en el navegador (evento y
// sessionStorage) para que el formulario existente la tome. Si el asistente no
// responde, el panel se retira y queda el formulario clasico.

import { useState } from "react";
import {
  CLAVES_PESO,
  prioridadDeOrden,
  validarEspec,
  type ClavePeso,
  type Componente,
} from "./espec";
import { Prioridades, ResumenRestricciones, SelectorPresupuesto, TarjetaPersonaje } from "./Componentes";
import estilos from "./Asistente.module.css";

export const EVENTO_RESTRICCIONES = "tukit:asistente-restricciones";
export const CLAVE_ALMACEN = "tukit:asistente-restricciones";

export interface RestriccionesConfirmadas {
  personajes: string[];
  presupuesto_por_hijo: number | null;
  prioridad: "precio" | "equilibrio" | "calidad";
  pesos: Record<ClavePeso, number>;
  disposicion_sobreprecio: number;
}

interface Propuesta {
  propuesta_id: string;
  ui: Componente[];
  preferencias: { pesos: Record<ClavePeso, number>; disposicion_sobreprecio: number };
}

const EJEMPLOS = [
  "Mi hijo ama Spiderman, quiero gastar poco pero que los colores sean buenos",
  "Que sea lo mejor aunque cueste más",
  "Algo equilibrado, sin pasarme de 300 mil",
];

async function avisarDecision(propuesta_id: string, decision: "aceptada" | "rechazada" | "editada") {
  try {
    await fetch("/api/asistente/decision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ propuesta_id, decision, tipo: "restricciones" }),
    });
  } catch {
    /* la bitacora no estorba */
  }
}

export default function PanelEmpezar() {
  const [texto, setTexto] = useState("");
  const [cargando, setCargando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [retirado, setRetirado] = useState(false);
  const [propuesta, setPropuesta] = useState<Propuesta | null>(null);
  const [editado, setEditado] = useState(false);
  const [presupuesto, setPresupuesto] = useState<number | null>(null);
  const [orden, setOrden] = useState<ClavePeso[]>([...CLAVES_PESO]);
  const [confirmado, setConfirmado] = useState(false);

  if (retirado) return null;

  async function interpretar() {
    if (!texto.trim() || cargando) return;
    setCargando(true);
    setAviso(null);
    setConfirmado(false);
    try {
      const respuesta = await fetch("/api/asistente/interpretar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });
      const cuerpo = (await respuesta.json().catch(() => null)) as Record<string, unknown> | null;
      if (respuesta.status === 503 || respuesta.status === 404) {
        setRetirado(true); // sin asistente: queda el formulario de siempre
        return;
      }
      if (!respuesta.ok || !cuerpo) {
        setAviso("No pudimos leer eso. Prueba de nuevo o llena el formulario de abajo.");
        return;
      }
      if (cuerpo["estado"] !== "propuesta") {
        setPropuesta(null);
        setAviso(typeof cuerpo["mensaje"] === "string" ? cuerpo["mensaje"] : "No entendimos bien. Cuéntanos de otra forma.");
        return;
      }
      const ui = validarEspec(cuerpo["ui"]);
      if (!ui) {
        setRetirado(true);
        return;
      }
      const prioridades = ui.componentes.find((c) => c.tipo === "Prioridades");
      const tope = ui.componentes.find((c) => c.tipo === "SelectorPresupuesto");
      setOrden(prioridades?.tipo === "Prioridades" ? prioridades.props.orden : [...CLAVES_PESO]);
      setPresupuesto(tope?.tipo === "SelectorPresupuesto" ? tope.props.valor : null);
      setEditado(false);
      setPropuesta({
        propuesta_id: String(cuerpo["propuesta_id"]),
        ui: ui.componentes,
        preferencias: cuerpo["preferencias"] as Propuesta["preferencias"],
      });
    } catch {
      setRetirado(true);
    } finally {
      setCargando(false);
    }
  }

  function confirmar() {
    if (!propuesta) return;
    const personajes = propuesta.ui.flatMap((c) => (c.tipo === "TarjetaPersonaje" ? [c.props.nombre] : []));
    // Los pesos de R se reordenan segun lo que el acudiente dejo arriba.
    const ordenados = [...CLAVES_PESO].map((k) => propuesta.preferencias.pesos[k]).sort((a, b) => b - a);
    const pesos = { ...propuesta.preferencias.pesos };
    orden.forEach((clave, i) => {
      pesos[clave] = ordenados[i] ?? 0;
    });
    const salida: RestriccionesConfirmadas = {
      personajes,
      presupuesto_por_hijo: presupuesto,
      prioridad: prioridadDeOrden(orden),
      pesos,
      disposicion_sobreprecio: propuesta.preferencias.disposicion_sobreprecio,
    };
    try {
      sessionStorage.setItem(CLAVE_ALMACEN, JSON.stringify(salida));
    } catch {
      /* sin almacenamiento, queda el evento */
    }
    window.dispatchEvent(new CustomEvent(EVENTO_RESTRICCIONES, { detail: salida }));
    void avisarDecision(propuesta.propuesta_id, editado ? "editada" : "aceptada");
    setConfirmado(true);
  }

  function descartar() {
    if (propuesta) void avisarDecision(propuesta.propuesta_id, "rechazada");
    setPropuesta(null);
    setConfirmado(false);
  }

  return (
    <section className={estilos.panel} aria-labelledby="asistente-titulo">
      <h2 id="asistente-titulo" className={estilos.titulo}>
        Cuéntanos qué necesitas
      </h2>
      <p className={estilos.ayuda}>
        Escríbelo como se lo dirías a una persona. Tú revisas todo antes de que pase al formulario.
      </p>
      <label className={estilos.rotulo} htmlFor="asistente-texto">
        Tu pedido
      </label>
      <textarea
        id="asistente-texto"
        className={estilos.entrada}
        value={texto}
        maxLength={1000}
        onChange={(e) => setTexto(e.target.value)}
        placeholder="Mi hijo ama Spiderman, quiero gastar poco pero que los colores sean buenos"
      />
      <div className={estilos.ejemplos}>
        {EJEMPLOS.map((ejemplo) => (
          <button key={ejemplo} type="button" className={estilos.ejemplo} onClick={() => setTexto(ejemplo)}>
            {ejemplo}
          </button>
        ))}
      </div>
      <div className={estilos.acciones}>
        <button type="button" className={estilos.primario} onClick={interpretar} disabled={cargando || !texto.trim()}>
          {cargando ? "Pensando…" : "Entender mi pedido"}
        </button>
      </div>
      <div aria-live="polite">{aviso && <p className={estilos.aviso}>{aviso}</p>}</div>

      {propuesta && (
        <div className={estilos.lista}>
          <p className={estilos.rotulo}>Esto entendimos. Cámbialo si algo no es así.</p>
          <ul className={estilos.lista}>
            {propuesta.ui.map((c, i) =>
              c.tipo === "TarjetaPersonaje" ? (
                <TarjetaPersonaje key={`p${i}`} nombre={c.props.nombre} imagen_url={c.props.imagen_url} />
              ) : null,
            )}
          </ul>
          {propuesta.ui.map((c, i) => {
            if (c.tipo === "SelectorPresupuesto") {
              return (
                <SelectorPresupuesto
                  key={`s${i}`}
                  {...c.props}
                  valor={presupuesto}
                  onCambio={(v) => {
                    setPresupuesto(v);
                    setEditado(true);
                    setConfirmado(false);
                  }}
                />
              );
            }
            if (c.tipo === "Prioridades") {
              return (
                <Prioridades
                  key={`o${i}`}
                  orden={orden}
                  onCambio={(o) => {
                    setOrden(o);
                    setEditado(true);
                    setConfirmado(false);
                  }}
                />
              );
            }
            return null;
          })}
          <ResumenRestricciones
            personajes={propuesta.ui.flatMap((c) => (c.tipo === "TarjetaPersonaje" ? [c.props.nombre] : []))}
            presupuesto={presupuesto}
            orden={orden}
          />
          {confirmado ? (
            <p className={estilos.exito} role="status">
              Listo. Pasamos esto al formulario; revisa los pasos de abajo y completa lo que falte.
            </p>
          ) : (
            <div className={estilos.acciones}>
              <button type="button" className={estilos.primario} onClick={confirmar}>
                Sí, usar esto
              </button>
              <button type="button" className={estilos.secundario} onClick={descartar}>
                No, prefiero el formulario
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
