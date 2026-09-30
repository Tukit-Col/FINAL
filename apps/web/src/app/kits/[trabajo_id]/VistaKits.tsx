"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Star, PiggyBank, Sparkles, Gem } from "lucide-react";
import { prefiereMenosMovimiento } from "@tukit/contrato/motion";
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
import { FalloApi, iniciarCheckout } from "@/lib/api-navegador";
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

export default function VistaKits({ trabajo, correo }: { trabajo: Trabajo; correo: string }) {
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

      <Checkout trabajoId={trabajo.trabajo_id} perfil={kit.perfil} total={kit.total} correo={correo} />
    </div>
  );
}

// El pago: se congela el precio del kit elegido y se manda al acudiente a la
// pasarela. No viaja ni un id de producto —el backend arma la orden desde el
// trabajo—; aqui solo se recoge a donde entregar y el correo del comprobante.
function Checkout({
  trabajoId,
  perfil,
  total,
  correo,
}: {
  trabajoId: string;
  perfil: PerfilKit;
  total: number;
  correo: string;
}) {
  const [abierto, setAbierto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datos, setDatos] = useState({
    destinatario: "",
    direccion: "",
    ciudad: "",
    // Prellenado con el correo de la sesion: al acudiente ya identificado no se
    // le vuelve a pedir. Editable por si el comprobante va a otro correo.
    correo,
  });
  const formRef = useRef<HTMLFormElement>(null);
  const primerCampoRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!abierto) return;
    // El form aparece bajo la barra fija del total; lo traemos a la vista y
    // enfocamos el primer campo. Con prefers-reduced-motion, sin animacion.
    formRef.current?.scrollIntoView({
      behavior: prefiereMenosMovimiento() ? "auto" : "smooth",
      block: "start",
    });
    primerCampoRef.current?.focus({ preventScroll: true });
  }, [abierto]);

  const cambiar = (campo: keyof typeof datos) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setDatos((d) => ({ ...d, [campo]: e.target.value }));

  async function pagar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const { destinatario, direccion, ciudad, correo } = datos;
      const checkout = await iniciarCheckout(trabajoId, {
        perfil,
        correo,
        entrega: { destinatario, direccion, ciudad },
        // La pasarela devuelve aqui tras pagar; el trabajo publicado es la
        // pagina de vuelta natural.
        url_redireccion: window.location.href,
      });
      if (checkout.url_redireccion) {
        window.location.href = checkout.url_redireccion;
      } else {
        // Sin pasarela (modo de prueba sin redireccion): el pedido quedo creado.
        setError(null);
        setAbierto(false);
        window.alert(`Pedido ${checkout.pedido_id} creado por ${formatearPesos(checkout.total)}.`);
      }
    } catch (causa) {
      const mensaje =
        causa instanceof FalloApi
          ? causa.message
          : "No pudimos iniciar el pago. Intenta de nuevo.";
      setError(mensaje);
      setEnviando(false);
    }
  }

  return (
    <>
      <footer className={styles.pie}>
        <div>
          <span className={styles.etiquetaTotal}>Total del kit {perfil}</span>
          <span className={`${styles.totalPie} cifra`}>{formatearPesos(total)}</span>
          <span className={styles.notaTotal}>
            Solo lo que Tukit te puede vender. Lo que gestiona el colegio no entra en
            esta cifra.
          </span>
        </div>
        {!abierto && (
          <button type="button" className={styles.pagar} onClick={() => setAbierto(true)}>
            Ir a pagar
          </button>
        )}
      </footer>

      {abierto && (
        <form ref={formRef} className={styles.formPago} onSubmit={pagar}>
          <p className={styles.tituloPago}>¿A dónde te lo llevamos?</p>
          <label>
            Nombre de quien recibe
            <input
              ref={primerCampoRef}
              value={datos.destinatario}
              onChange={cambiar("destinatario")}
              required
            />
          </label>
          <label>
            Dirección
            <input value={datos.direccion} onChange={cambiar("direccion")} required />
          </label>
          <label>
            Ciudad
            <input value={datos.ciudad} onChange={cambiar("ciudad")} required />
          </label>
          {/* El correo solo se pide a quien no tiene sesion: al acudiente ya
              identificado no se le vuelve a pedir, su comprobante va al correo
              de la cuenta. Anonimo => el campo aparece y es obligatorio. */}
          {correo ? (
            <p className={styles.notaTotal}>
              El comprobante va a <strong>{correo}</strong>.
            </p>
          ) : (
            <label>
              Correo para el comprobante
              <input type="email" value={datos.correo} onChange={cambiar("correo")} required />
            </label>
          )}
          {error && <p className={styles.errorPago}>{error}</p>}
          <button type="submit" className={styles.pagar} disabled={enviando}>
            {enviando ? "Llevándote a la pasarela…" : `Pagar ${formatearPesos(total)}`}
          </button>
        </form>
      )}

      <p className={styles.notaPago}>
        Al confirmar, el precio se congela y no se mueve. Pagas en la pasarela segura;
        Tukit nunca ve los datos de tu tarjeta.
      </p>
    </>
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
