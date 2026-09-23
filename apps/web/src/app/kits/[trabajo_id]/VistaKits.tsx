"use client";

import { useMemo, useState } from "react";
import { Star, Lock, PiggyBank, Sparkles, Gem } from "lucide-react";
import {
  ORDEN_SECCIONES,
  TITULO_CLASE,
  agruparPorClase,
  clasificar,
  formatearPesos,
  type ClaseLinea,
  type Kit,
  type PerfilKit,
  type Trabajo,
} from "@tukit/contrato";
import LineaDeKit from "./LineaDeKit";
import styles from "./Kits.module.css";

// Un icono por perfil, para que los tres kits se distingan de un vistazo.
const ICONO_PERFIL: Record<PerfilKit, typeof PiggyBank> = {
  Ahorrador: PiggyBank,
  Fan: Sparkles,
  Premium: Gem,
};

// Que promete cada perfil, en una frase. Los tres tienen el MISMO alcance:
// lo que cambia es el punto del frente de Pareto, no cuanto te resuelven.
const PROMESA: Record<PerfilKit, string> = {
  Ahorrador: "Lo más barato que cumple con la lista.",
  Fan: "Con los personajes que pidió tu hijo, donde se puede.",
  Premium: "Las marcas que más aguantan el año.",
};

// Las secciones que NO se cobran se explican una vez, arriba del grupo, en
// vez de repetir la misma aclaracion en cada renglon.
const EXPLICACION_SECCION: Partial<Record<ClaseLinea, string>> = {
  hueco: "Entendimos qué pide la lista y hoy no lo tenemos. Preferimos decirlo a ofrecerte otra cosa parecida como si fuera esto.",
  sin_match: "Estos renglones no los supimos leer. Quedan visibles para que no se te pasen.",
  pendiente_revision: "Habia varias opciones parecidas y ninguna ganaba clara.",
  licencia_digital: "Se pagan por fuera de Tukit, en la plataforma del proveedor.",
  informativa: "El colegio o la editorial los venden directamente. No los podemos cobrar, pero sí decirte cómo conseguirlos.",
  diferido: "El colegio los va a pedir durante el año.",
  no_comprar: "El colegio dice que uses el que ya tienes en casa.",
  fuera_de_alcance: "Los uniformes todavía no los surtimos.",
  comprable: undefined,
};

export default function VistaKits({ trabajo }: { trabajo: Trabajo }) {
  const recomendado = trabajo.recomendado;
  const [activo, setActivo] = useState<PerfilKit>(recomendado?.perfil ?? "Ahorrador");

  const kit = useMemo(
    () => trabajo.kits.find((k) => k.perfil === activo) ?? trabajo.kits[0],
    [trabajo.kits, activo],
  );

  if (!kit) {
    return (
      <div className={styles.pagina}>
        <p className={styles.vacio}>Este pedido no trajo ningún kit.</p>
      </div>
    );
  }

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <h1>Tus tres kits están listos</h1>
        <p>
          Los tres cubren la misma lista. Te marcamos uno, pero los otros dos siguen
          aquí: cuál conviene depende de cosas que solo sabes tú.
        </p>
      </header>

      {/* ---------------------------------------------- Comparador de kits */}
      <div className={styles.comparador} role="tablist" aria-label="Los tres kits">
        {trabajo.kits.map((otro) => {
          const esRecomendado = otro.perfil === recomendado?.perfil;
          const esActivo = otro.perfil === activo;
          const IconoKit = ICONO_PERFIL[otro.perfil];
          return (
            <button
              key={otro.perfil}
              role="tab"
              aria-selected={esActivo}
              className={`${styles.tarjetaKit} ${esActivo ? styles.kitActivo : ""} ${
                esRecomendado ? styles.kitRecomendado : ""
              }`}
              onClick={() => setActivo(otro.perfil)}
            >
              {esRecomendado && (
                <span className={styles.chapaRecomendado}>
                  <Star size={12} aria-hidden="true" fill="currentColor" strokeWidth={0} />
                  Te recomendamos este
                </span>
              )}
              <span className={styles.nombreKit}>
                <span className={styles.iconoKit} aria-hidden="true">
                  <IconoKit size={18} strokeWidth={2.4} />
                </span>
                {otro.perfil}
              </span>
              <span className={`${styles.totalKit} cifra`}>{formatearPesos(otro.total)}</span>
              <span className={styles.promesa}>{PROMESA[otro.perfil]}</span>
              <span className={styles.objetivos}>
                {Math.round(otro.objetivos.disponibilidad * 100)}% con precio confirmado
              </span>
            </button>
          );
        })}
      </div>

      {recomendado && (
        <p className={styles.razon}>
          <strong>Por qué el {recomendado.perfil}:</strong> {recomendado.razon}
          {!recomendado.dentro_de_presupuesto && (
            <em className={styles.fueraPresupuesto}> Ojo: se pasa del tope que pusiste.</em>
          )}
        </p>
      )}

      <ResumenKit kit={kit} />

      {kit.consolidaciones.length > 0 && (
        <section className={styles.consolidaciones}>
          <h2>Lo que juntamos entre tus hijos</h2>
          <ul>
            {kit.consolidaciones.map((c) => (
              <li key={c.concepto}>
                <strong>{c.explicacion}</strong>
                <span>
                  {c.concepto} · {c.hijos.join(" y ")} · ahorras{" "}
                  <span className="cifra">{formatearPesos(c.ahorro)}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <SeccionesDeLineas kit={kit} />

      <footer className={styles.pie}>
        <div>
          <span className={styles.etiquetaTotal}>Total del kit {kit.perfil}</span>
          <span className={`${styles.totalPie} cifra`}>{formatearPesos(kit.total)}</span>
          <span className={styles.notaTotal}>
            Solo lo que Tukit te puede vender. Lo que gestiona el colegio no entra en
            esta cifra.
          </span>
        </div>
        {/* El pago vive en `comercio` y todavia no existe. Un boton que no
            hace nada es peor que un boton apagado que dice por que. */}
        <button type="button" className={styles.pagar} disabled>
          <Lock size={17} aria-hidden="true" strokeWidth={2.4} />
          Ir a pagar
        </button>
      </footer>
      <p className={styles.notaPago}>
        El pago se habilita cuando el servicio de comercio esté arriba. Al confirmar,
        el precio se congela y no se mueve.
      </p>
    </div>
  );
}

function ResumenKit({ kit }: { kit: Kit }) {
  const grupos = agruparPorClase(kit.lineas);
  const comprables = grupos.get("comprable")?.length ?? 0;
  const huecos = (grupos.get("hueco")?.length ?? 0) + (grupos.get("sin_match")?.length ?? 0);
  const gestionaColegio =
    (grupos.get("informativa")?.length ?? 0) +
    (grupos.get("licencia_digital")?.length ?? 0) +
    (grupos.get("diferido")?.length ?? 0);

  return (
    <dl className={styles.resumen}>
      <div>
        <dt>En tu carrito</dt>
        <dd className="cifra">{comprables}</dd>
      </div>
      <div className={huecos > 0 ? styles.resumenAviso : ""}>
        <dt>No los tenemos</dt>
        <dd className="cifra">{huecos}</dd>
      </div>
      <div>
        <dt>Los gestiona el colegio</dt>
        <dd className="cifra">{gestionaColegio}</dd>
      </div>
      <div>
        <dt>Renglones de la lista</dt>
        <dd className="cifra">{kit.lineas.length}</dd>
      </div>
    </dl>
  );
}

function SeccionesDeLineas({ kit }: { kit: Kit }) {
  const grupos = agruparPorClase(kit.lineas);

  return (
    <div className={styles.secciones}>
      {ORDEN_SECCIONES.map((clase) => {
        const lineas = grupos.get(clase);
        if (!lineas || lineas.length === 0) return null;
        const explicacion = EXPLICACION_SECCION[clase];
        return (
          <section key={clase} className={`${styles.seccion} ${styles[`seccion_${clase}`] ?? ""}`}>
            <header className={styles.cabeceraSeccion}>
              <h2>
                {TITULO_CLASE[clase]}{" "}
                <span className={`${styles.conteo} cifra`}>{lineas.length}</span>
              </h2>
              {explicacion && <p>{explicacion}</p>}
            </header>
            <ul className={styles.lineas}>
              {lineas.map((linea) => (
                <LineaDeKit key={linea.item_id} linea={linea} clase={clasificar(linea)} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
