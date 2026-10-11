"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Star, PiggyBank, Sparkles, Gem, SlidersHorizontal } from "lucide-react";
import { prefiereMenosMovimiento } from "@tukit/contrato/motion";
import {
  ORDEN_SECCIONES,
  TITULO_CLASE,
  agruparPorClase,
  clasificar,
  esBogota,
  formatearPesos,
  LOCALIDADES_BOGOTA,
  type ClaseLinea,
  type Kit,
  type PerfilKit,
  type Trabajo,
} from "@tukit/contrato";
import { FalloApi, iniciarCheckout } from "@/lib/api-navegador";
import { escribirDireccionAMano } from "@/lib/direccion-checkout";
import { abrirWidgetWompi } from "@/lib/wompi";
import CampoDireccion, { type LugarElegido } from "./CampoDireccion";
import LineaDeKit from "./LineaDeKit";
import styles from "./Kits.module.css";

// Un icono por perfil, para que los kits se distingan de un vistazo.
const ICONO_PERFIL: Record<PerfilKit, typeof PiggyBank> = {
  Ahorrador: PiggyBank,
  Fan: Sparkles,
  "A tu Medida": SlidersHorizontal,
  Premium: Gem,
};

// Que promete cada perfil, en una frase. Todos tienen el MISMO alcance: lo que
// cambia es el punto del frente de Pareto, no cuanto te resuelven.
const PROMESA: Record<PerfilKit, string> = {
  Ahorrador: "Lo más barato que cumple con la lista.",
  Fan: "Con los personajes que pidió tu hijo, donde se puede.",
  "A tu Medida": "La mejor marca que cabe en lo que quieres gastar.",
  Premium: "Las marcas que más aguantan el año.",
};

// Del más barato al de mejor marca: Ahorrador y Premium en las puntas y, entre
// ellos, los que el acudiente pidió (Fan, A tu Medida).
const ORDEN_PERFIL: PerfilKit[] = ["Ahorrador", "Fan", "A tu Medida", "Premium"];

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
  por_su_cuenta: "Tukit no los vende. Te los dejamos visibles para que los consigas por tu cuenta.",
  comprable: undefined,
};

export default function VistaKits({
  trabajo,
  correo,
  llaveMaps,
}: {
  trabajo: Trabajo;
  correo: string;
  llaveMaps: string | null;
}) {
  const recomendado = trabajo.recomendado;
  const [activo, setActivo] = useState<PerfilKit>(recomendado?.perfil ?? "Ahorrador");
  const kits = useMemo(
    () =>
      [...trabajo.kits].sort(
        (a, b) => ORDEN_PERFIL.indexOf(a.perfil) - ORDEN_PERFIL.indexOf(b.perfil),
      ),
    [trabajo.kits],
  );

  const kit = useMemo(() => kits.find((k) => k.perfil === activo) ?? kits[0], [kits, activo]);

  if (!kit) {
    return (
      <div className={styles.pagina}>
        <p className={styles.vacio}>Este pedido no trajo ningún kit.</p>
      </div>
    );
  }

  // En la ruta rápida el "recomendado" es el kit que el acudiente eligió al
  // empezar; en los demás trabajos, el que marcó el recomendador.
  const eligioEl = trabajo.origen === "parent_apply";
  const rotuloMarcado = eligioEl ? "Tu elección" : "Te recomendamos este";
  const IconoActivo = ICONO_PERFIL[kit.perfil];
  const viendoOtro = recomendado !== null && kit.perfil !== recomendado.perfil;

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <h1>{eligioEl ? "Tu kit está listo" : "Tus kits están listos"}</h1>
        <p>
          {eligioEl
            ? "Este es el kit que elegiste. Si quieres, compáralo con los otros o cambia cualquier producto por otra opción."
            : "Todos cubren la misma lista. Te marcamos uno, pero los demás siguen aquí: cuál conviene depende de cosas que solo sabes tú."}
        </p>
      </header>

      {/* ------------------------------------- Selector discreto de kits. Los
          tres siguen a un clic (el contrato exige mostrarlos), pero no
          compiten con el kit que se está mirando. */}
      {kits.length > 1 && (
        <div className={styles.selectorKits} role="tablist" aria-label="Ver otro kit">
          <span className={styles.selectorRotulo}>Ver kit</span>
          {kits.map((otro) => {
            const esActivo = otro.perfil === kit.perfil;
            const esMarcado = otro.perfil === recomendado?.perfil;
            return (
              <button
                key={otro.perfil}
                type="button"
                role="tab"
                aria-selected={esActivo}
                className={`${styles.opcionKit} ${esActivo ? styles.opcionKitActiva : ""}`}
                onClick={() => setActivo(otro.perfil)}
                title={esMarcado ? rotuloMarcado : undefined}
              >
                {esMarcado && (
                  <Star
                    size={12}
                    aria-label={rotuloMarcado}
                    fill="currentColor"
                    strokeWidth={0}
                    className={styles.estrellaKit}
                  />
                )}
                {otro.perfil}
                <span className={`${styles.totalOpcion} cifra`}>{formatearPesos(otro.total)}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ------------------------------------------------ El kit que se mira */}
      <section className={`${styles.tarjetaKit} ${styles.kitActivo}`} aria-live="polite">
        {kit.perfil === recomendado?.perfil && (
          <span className={styles.chapaRecomendado}>
            <Star size={12} aria-hidden="true" fill="currentColor" strokeWidth={0} />
            {rotuloMarcado}
          </span>
        )}
        <span className={styles.nombreKit}>
          <span className={styles.iconoKit} aria-hidden="true">
            <IconoActivo size={18} strokeWidth={2.4} />
          </span>
          {kit.perfil}
        </span>
        <span className={`${styles.totalKit} cifra`}>{formatearPesos(kit.total)}</span>
        <span className={styles.promesa}>{PROMESA[kit.perfil]}</span>
        {/* Un kit sin objetivos (los de la ruta rápida anteriores al
            cálculo) no pinta la línea: mejor nada que "NaN%". */}
        {Number.isFinite(kit.objetivos?.disponibilidad) && (
          <span className={styles.objetivos}>
            {Math.round(kit.objetivos.disponibilidad * 100)}% con precio confirmado
          </span>
        )}
      </section>

      {viendoOtro ? (
        <p className={styles.razon}>
          Estás viendo el kit <strong>{kit.perfil}</strong>. Si lo pagas, es este el que te
          llevamos.{" "}
          <button
            type="button"
            className={styles.volverKit}
            onClick={() => setActivo(recomendado.perfil)}
          >
            Volver a {eligioEl ? "mi kit" : "el recomendado"} ({recomendado.perfil})
          </button>
        </p>
      ) : (
        recomendado && (
          <p className={styles.razon}>
            <strong>
              {eligioEl ? "Tu kit:" : `Por qué el ${recomendado.perfil}:`}
            </strong>{" "}
            {recomendado.razon}
            {/* `null` es "no puso tope": solo `false` es pasarse. */}
            {recomendado.dentro_de_presupuesto === false && (
              <em className={styles.fueraPresupuesto}> Ojo: se pasa del tope que pusiste.</em>
            )}
          </p>
        )
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

      <SeccionesDeLineas kit={kit} trabajoId={trabajo.trabajo_id} />

      <Checkout
        trabajoId={trabajo.trabajo_id}
        perfil={kit.perfil}
        total={kit.total}
        correo={correo}
        llaveMaps={llaveMaps}
      />
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
  llaveMaps,
}: {
  trabajoId: string;
  perfil: PerfilKit;
  total: number;
  correo: string;
  // La llave de Google Places, leida en el servidor; `null` => campos manuales.
  llaveMaps: string | null;
}) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datos, setDatos] = useState({
    destinatario: "",
    direccion: "",
    indicaciones: "",
    ciudad: "",
    localidad: "",
    departamento: "",
    // Solo si la direccion salio de una sugerencia de Google y no se edito.
    google_place_id: "",
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

  const cambiar =
    (campo: keyof typeof datos) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setDatos((d) => ({ ...d, [campo]: e.target.value }));

  // La localidad solo aplica en Bogota: fuera de ella el campo se apaga y no
  // viaja, aunque el acudiente la hubiera elegido antes de cambiar la ciudad.
  const enBogota = esBogota(datos.ciudad);

  // Editar la direccion a mano la desliga del lugar de Google que se eligio, y
  // suelta la localidad que Google derivo de el (`direccion-checkout.ts`).
  const escribirDireccion = (direccion: string) =>
    setDatos((d) => escribirDireccionAMano(d, direccion));

  // Elegir una sugerencia fija la direccion de Google y pre-llena lo que se
  // pudo derivar. Ciudad y departamento que Google no trajo conservan lo
  // escrito; la localidad siempre se reemplaza (la anterior era de otra
  // direccion) y, si no se pudo derivar, queda vacia para elegirla.
  const elegirLugar = (lugar: LugarElegido) =>
    setDatos((d) => ({
      ...d,
      direccion: lugar.direccion,
      google_place_id: lugar.google_place_id ?? "",
      ciudad: lugar.ciudad || d.ciudad,
      localidad: lugar.localidad,
      departamento: lugar.departamento || d.departamento,
    }));

  async function pagar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const { destinatario, direccion, ciudad, correo } = datos;
      // Los opcionales vacios no viajan: el cuerpo de quien no los llena es el
      // mismo de siempre.
      const opcionales = {
        indicaciones: datos.indicaciones.trim(),
        localidad: enBogota ? datos.localidad : "",
        departamento: datos.departamento.trim(),
        google_place_id: datos.google_place_id,
      };
      const checkout = await iniciarCheckout(trabajoId, {
        perfil,
        correo,
        entrega: {
          destinatario,
          direccion,
          ciudad,
          ...Object.fromEntries(Object.entries(opcionales).filter(([, valor]) => valor)),
        },
        // La pasarela simulada redirige aqui; con Wompi, solo PSE (que se lleva
        // la pestana al banco) vuelve por esta URL.
        url_redireccion: `${window.location.origin}/pago/resultado`,
      });
      if (checkout.widget) {
        // Wompi abre el pago en un modal encima del kit. Al terminar, el id
        // de la transaccion va a la pagina de resultado, que lo confirma con
        // el servidor (el callback del widget es solo informativo).
        await abrirWidgetWompi(checkout.widget, (transaccionId) => {
          router.push(`/pago/resultado?id=${encodeURIComponent(transaccionId)}`);
        });
        // El modal ya cubre la pagina. Si el acudiente lo cierra sin pagar, el
        // boton vuelve a quedar disponible.
        setEnviando(false);
      } else if (checkout.url_redireccion) {
        window.location.href = checkout.url_redireccion;
      } else {
        setError("No pudimos abrir la pasarela de pago.");
        setEnviando(false);
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
          <CampoDireccion
            llave={llaveMaps}
            valor={datos.direccion}
            onEscribir={escribirDireccion}
            onElegir={elegirLugar}
          />
          <label>
            Apartamento, torre, interior o indicaciones (opcional)
            <input
              value={datos.indicaciones}
              onChange={cambiar("indicaciones")}
              maxLength={512}
              autoComplete="address-line2"
            />
          </label>
          <div className={styles.filaPago}>
            <label>
              Ciudad
              <input
                value={datos.ciudad}
                onChange={cambiar("ciudad")}
                required
                autoComplete="address-level2"
              />
            </label>
            <label>
              Localidad
              <select
                value={enBogota ? datos.localidad : ""}
                onChange={cambiar("localidad")}
                required={enBogota}
                disabled={!enBogota}
              >
                <option value="">{enBogota ? "Elige la localidad" : "Solo en Bogotá"}</option>
                {LOCALIDADES_BOGOTA.map((localidad) => (
                  <option key={localidad} value={localidad}>
                    {localidad}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Departamento (opcional)
            <input
              value={datos.departamento}
              onChange={cambiar("departamento")}
              maxLength={128}
              autoComplete="address-level1"
            />
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

function SeccionesDeLineas({ kit, trabajoId }: { kit: Kit; trabajoId: string }) {
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
                <LineaDeKit
                  key={linea.item_id}
                  linea={linea}
                  clase={clasificar(linea)}
                  trabajoId={trabajoId}
                  perfil={kit.perfil}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
