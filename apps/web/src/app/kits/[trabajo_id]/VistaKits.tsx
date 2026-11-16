"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Star,
  PiggyBank,
  Sparkles,
  Gem,
  SlidersHorizontal,
  BookOpen,
  Shirt,
  CircleAlert,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  House,
  School,
  ShoppingBag,
  NotebookPen,
  Pencil,
  Palette,
  Paperclip,
  Ruler,
  Package,
  type LucideIcon,
} from "lucide-react";
import { prefiereMenosMovimiento } from "@tukit/contrato/motion";
import {
  agruparPorClase,
  clasificar,
  dondeComprar,
  esLibro,
  esUniforme,
  estadoDePrecio,
  formatearPesos,
  hayQueCobrar,
  LOCALIDADES_BOGOTA,
  personajesPorHijo,
  razonDeNoCobrar,
  type ClaseLinea,
  type LineaKit,
  type Kit,
  type PerfilKit,
  type Trabajo,
} from "@tukit/contrato";
import { FalloApi, iniciarCheckout } from "@/lib/api-navegador";
import { escribirDireccionAMano } from "@/lib/direccion-checkout";
import type { EntregaPrevia } from "@/lib/pagar-pedido";
import {
  agruparPorCategoria,
  categoriaDeLinea,
  etiquetasDeHijos,
  gradosDeHijos,
  idAnclaCategoria,
  notaSinEncaje,
  personajeLegible,
  resumenPorHijo,
  fotoDeConsolidacion,
  textoDeConsolidacion,
  type ApodoMatricula,
  type CategoriaKit,
  type ResumenHijo,
} from "@/lib/kit-vista";
import { abrirWidgetWompi } from "@/lib/wompi";
import CampoDireccionOsm, { type LugarElegido } from "./CampoDireccionOsm";
import LineaDeKit from "./LineaDeKit";
import CabeceraCategoria from "./CabeceraCategoria";
import AsistenteKitSlot from "./AsistenteKitSlot";
import TarjetaLuz from "@/components/TarjetaLuz";
import ResumenRecibo from "./ResumenRecibo";
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

// La ciudad de entrega: fija, sin forma de cambiarla.
const CIUDAD_ENTREGA = "Bogotá";

export default function VistaKits({
  trabajo,
  correo,
  matriculas,
  entregaPrevia,
  abrirPago,
}: {
  trabajo: Trabajo;
  correo: string;
  // Colegio, grado y apodo de los hijos del portador (vacio sin sesion).
  matriculas: ApodoMatricula[];
  entregaPrevia: EntregaPrevia | null;
  abrirPago: boolean;
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

  // El nombre de cada hijo del kit: su apodo, "Hijo N" o nada; nunca la
  // referencia interna con la que viaja cada renglon.
  const nombresHijos = useMemo(
    () =>
      etiquetasDeHijos(
        trabajo.kits.flatMap((k) => k.lineas.map((l) => l.hijo)),
        trabajo.hijos,
        matriculas,
      ),
    [trabajo.kits, trabajo.hijos, matriculas],
  );
  const gradosHijos = useMemo(
    () => gradosDeHijos(trabajo.kits.flatMap((k) => k.lineas.map((l) => l.hijo)), trabajo.hijos),
    [trabajo.kits, trabajo.hijos],
  );
  // El resumen por hijo del kit que se mira (solo se pinta con 2+ hijos).
  const resumen = useMemo(
    () =>
      kit ? resumenPorHijo(kit, nombresHijos, gradosHijos, trabajo.personajes_por_hijo) : [],
    [kit, nombresHijos, gradosHijos, trabajo.personajes_por_hijo],
  );

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
                <span className={`${styles.totalOpcion} cifra`}>
                  {hayQueCobrar(otro.total) ? formatearPesos(otro.total) : "—"}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* ------------------------------------------------ El kit que se mira */}
      <TarjetaLuz key={`luz-${kit.perfil}`} className={`${styles.tarjetaKit} ${styles.kitActivo}`} aria-live="polite">
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
        <span className={`${styles.totalKit} cifra`}>
          {hayQueCobrar(kit.total) ? formatearPesos(kit.total) : "Sin productos con precio"}
        </span>
        <span className={styles.promesa}>{PROMESA[kit.perfil]}</span>
        {/* Un kit sin objetivos (los de la ruta rápida anteriores al
            cálculo) no pinta la línea: mejor nada que "NaN%". */}
        {Number.isFinite(kit.objetivos?.disponibilidad) && (
          <span className={styles.objetivos}>
            {Math.round(kit.objetivos.disponibilidad * 100)}% con precio confirmado
          </span>
        )}
      </TarjetaLuz>

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
        recomendado &&
        (!eligioEl || recomendado.dentro_de_presupuesto === false) && (
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

      {kit.perfil === "Fan" && resumen.length <= 1 && (
        <FranjaFan
          lineas={kit.lineas}
          pedidos={trabajo.personajes_por_hijo}
          sinEncaje={kit.personaje_sin_encaje ?? []}
          nombresHijos={nombresHijos}
        />
      )}

      {kit.consolidaciones.length > 0 && resumen.length <= 1 && (
        <section className={styles.consolidaciones}>
          <h2>Lo que juntamos entre tus hijos</h2>
          <p className={styles.explicaJunto}>
            Estos productos son iguales para varios de tus hijos, así que los compramos juntos y sobra menos.
          </p>
          <ul>
            {kit.consolidaciones.map((c, i) => {
              const t = textoDeConsolidacion(
                c,
                nombresHijos,
                c.ahorro > 0 ? formatearPesos(c.ahorro) : null,
                gradosHijos,
              );
              return (
                <li key={`${c.producto}-${i}`}>
                  <strong>{c.producto}</strong>
                  <span>
                    {[t.paraQuienes, t.cantidad].filter(Boolean).join(" · ")}
                  </span>
                  {t.porque && <span className={styles.porqueJunto}>{t.porque}</span>}
                  {t.ahorro && <span className={styles.ahorroJunto}>{t.ahorro}</span>}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {resumen.length > 1 && (
        <ResumenPorHijo
          key={`hijos-${kit.perfil}`}
          kit={kit}
          resumen={resumen}
          nombresHijos={nombresHijos}
          gradosHijos={gradosHijos}
          pedidos={trabajo.personajes_por_hijo}
        />
      )}

      <SeccionesDeLineas kit={kit} trabajoId={trabajo.trabajo_id} nombresHijos={nombresHijos} />

      <AsistenteKitSlot trabajoId={trabajo.trabajo_id} perfil={kit.perfil} />

      <ResumenRecibo
        perfil={kit.perfil}
        renglones={agruparPorCategoria(
          kit.lineas.filter((l) => clasificar(l) === "comprable" && !l.descartado),
        ).map((g) => ({ clave: g.categoria, titulo: g.titulo, cantidad: g.lineas.length }))}
        total={hayQueCobrar(kit.total) ? formatearPesos(kit.total) : "Sin productos con precio"}
      />

      <Checkout
        trabajoId={trabajo.trabajo_id}
        perfil={kit.perfil}
        total={kit.total}
        correo={correo}
        entregaPrevia={entregaPrevia}
        abrirPago={abrirPago}
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
  entregaPrevia,
  abrirPago,
}: {
  trabajoId: string;
  perfil: PerfilKit;
  total: number;
  correo: string;
  // La entrega del pedido pendiente de este kit (reintento tras un rechazo).
  entregaPrevia: EntregaPrevia | null;
  // Llegar con el formulario de entrega ya abierto ("Intentar de nuevo").
  abrirPago: boolean;
}) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(abrirPago);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datos, setDatos] = useState({
    destinatario: "",
    direccion: "",
    indicaciones: "",
    localidad: "",
    departamento: "",
    // Campo heredado del contrato de Comercio; el checkout ya no lo llena.
    google_place_id: "",
    // El pin confirmado en el mapa de OpenStreetMap.
    latitud: null as number | null,
    longitud: null as number | null,
    // Tras un pago rechazado, la entrega que ya se habia escrito.
    ...entregaPrevia,
    // La entrega es solo en Bogota: una entrega previa de otra ciudad no la cambia.
    ciudad: CIUDAD_ENTREGA,
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
    (campo: Exclude<keyof typeof datos, "ciudad" | "latitud" | "longitud">) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setDatos((d) => ({ ...d, [campo]: e.target.value }));

  // Editar la direccion a mano la desliga del lugar que se eligio, y suelta la
  // localidad y el pin derivados de el (`direccion-checkout.ts`).
  const escribirDireccion = (direccion: string) =>
    setDatos((d) => escribirDireccionAMano(d, direccion));

  // Elegir un resultado fija la direccion y pre-llena lo que se pudo derivar. El
  // departamento que no se derivo conserva lo escrito; la localidad siempre se
  // reemplaza (la anterior era de otra direccion) y, si no se pudo derivar, queda vacia para elegirla.
  const elegirLugar = (lugar: LugarElegido) =>
    setDatos((d) =>
      ({
        ...d,
        direccion: lugar.direccion,
        google_place_id: lugar.google_place_id ?? "",
        latitud: lugar.latitud ?? null,
        longitud: lugar.longitud ?? null,
        localidad: lugar.localidad,
        departamento: lugar.departamento || d.departamento,
      }),
    );

  // Mover el pin confirma otro punto sin tocar el texto ni la localidad.
  const moverPin = (latitud: number, longitud: number) =>
    setDatos((d) => ({ ...d, latitud, longitud }));

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
        localidad: datos.localidad,
        departamento: datos.departamento.trim(),
        google_place_id: datos.google_place_id,
        // Juntas o ninguna: Comercio rechaza una sola.
        latitud: datos.latitud !== null && datos.longitud !== null ? datos.latitud : undefined,
        longitud: datos.latitud !== null && datos.longitud !== null ? datos.longitud : undefined,
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
      {/* La franja pegada abajo lleva solo el total y el boton: en el celular
          cualquier renglon de mas tapa el kit que se esta mirando. La
          aclaracion de que entra en el total va justo encima, en el flujo. */}
      <p className={styles.notaTotalKit}>
        El total incluye solo lo que está en tu carrito. Lo de la sección «Fuera
        del carrito» no entra en esta cifra.
      </p>
      <footer className={styles.pie}>
        <div>
          <span className={styles.etiquetaTotal}>Total del kit {perfil}</span>
          <span className={`${styles.totalPie} cifra`}>
            {hayQueCobrar(total) ? formatearPesos(total) : "Sin productos con precio"}
          </span>
        </div>
        {!abierto && (
          <button
            type="button"
            className={styles.pagar}
            disabled={!hayQueCobrar(total)}
            onClick={() => setAbierto(true)}
          >
            Ir a pagar
          </button>
        )}
      </footer>

      {abierto && (
        <form ref={formRef} className={styles.formPago} onSubmit={pagar}>
          <p className={styles.tituloPago}>¿A dónde te lo llevamos?</p>
          <p className={styles.totalAntesDePagar}>
            Vas a pagar <strong className="cifra">{formatearPesos(total)}</strong> por el kit {perfil}.
          </p>
          <label>
            Nombre de quien recibe
            <input
              ref={primerCampoRef}
              value={datos.destinatario}
              onChange={cambiar("destinatario")}
              required
            />
          </label>
          {/* Búsqueda en OpenStreetMap con mapa de confirmación (ADR 0049). */}
          <CampoDireccionOsm
            valor={datos.direccion}
            latitud={datos.latitud}
            longitud={datos.longitud}
            onEscribir={escribirDireccion}
            onElegir={elegirLugar}
            onMoverPin={moverPin}
          />
          <label>
            Apto, torre, conjunto, referencias (opcional)
            <input
              value={datos.indicaciones}
              onChange={cambiar("indicaciones")}
              maxLength={120}
              autoComplete="address-line2"
            />
          </label>
          <div className={styles.filaPago}>
            <label>
              Ciudad
              <input value={datos.ciudad} readOnly aria-describedby="ciudad-fija" autoComplete="address-level2" />
            </label>
            <label>
              Localidad
              <select value={datos.localidad} onChange={cambiar("localidad")} required>
                <option value="">Elige la localidad</option>
                {LOCALIDADES_BOGOTA.map((localidad) => (
                  <option key={localidad} value={localidad}>
                    {localidad}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p id="ciudad-fija" className={styles.ciudadFija}>
            Por ahora entregamos solo en Bogotá.
          </p>
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
          <p className={styles.avisoLegal}>
            Al pagar aceptas los <Link href="/legal/terminos">términos y condiciones</Link>, la{" "}
            <Link href="/legal/privacidad">política de datos personales</Link> y conoces tu{" "}
            <Link href="/legal/retracto">derecho de retracto y garantía</Link>.
          </p>
          <button type="submit" className={styles.pagar} disabled={enviando || !hayQueCobrar(total)}>
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

// El icono del útil cuando el producto no trae foto: dice qué es, en vez de
// un "sin foto" que no dice nada.
const ICONO_CATEGORIA: Record<CategoriaKit, LucideIcon> = {
  cuadernos: NotebookPen,
  escritura: Pencil,
  arte: Palette,
  papeleria: Paperclip,
  geometria: Ruler,
  otros: Package,
};

type FilaSinEncaje = { hijo: string; concepto: string; personaje: string };

function FranjaFan({
  lineas,
  pedidos,
  sinEncaje,
  nombresHijos,
}: {
  lineas: LineaKit[];
  pedidos?: Record<string, string[]>;
  sinEncaje: FilaSinEncaje[];
  nombresHijos: Map<string, string>;
}) {
  // Con `pedidos` solo cuenta el personaje que pidió cada hijo; un trabajo
  // viejo sin ese campo cuenta cualquier personaje, como antes.
  const grupos = personajesPorHijo(lineas, pedidos);
  if (grupos.length === 0 && sinEncaje.length === 0) return null;
  const hijos = [...new Set([...grupos.map((g) => g.hijo), ...sinEncaje.map((f) => f.hijo)])];
  const total = grupos.reduce((n, g) => n + g.lineas.length, 0);
  const varios = hijos.length > 1;
  const personajes = [...new Set(grupos.map((g) => g.personaje))];

  if (!varios) {
    const productos = grupos.flatMap((g) => g.lineas);
    const notas = sinEncaje;
    return (
      <section className={styles.franjaFan} aria-labelledby="titulo-franja-fan">
        <h2 id="titulo-franja-fan">
          {personajes.length === 1 ? `Tu kit de ${personajes[0]}` : "Tu kit con personajes"}
        </h2>
        {productos.length > 0 && (
          <p>
            Por esto es el kit Fan: {productos.length} {productos.length === 1 ? "producto" : "productos"} con
            el personaje que pidió tu hijo. Abajo está la lista completa.
          </p>
        )}
        <TarjetasFan lineas={productos} />
        <NotasSinEncaje filas={notas} />
      </section>
    );
  }

  return (
    <section className={styles.franjaFan} aria-labelledby="titulo-franja-fan">
      <h2 id="titulo-franja-fan">Tu kit con personajes</h2>
      <p>
        Por esto es el kit Fan: {total} {total === 1 ? "producto" : "productos"} con los personajes que
        pidieron tus hijos. Abajo está la lista completa.
      </p>
      {hijos.map((hijo, i) => {
        const suyos = grupos.filter((g) => g.hijo === hijo);
        const productos = suyos.flatMap((g) => g.lineas);
        const nombre = nombresHijos.get(hijo) ?? `Hijo ${i + 1}`;
        const personaje =
          suyos[0]?.personaje ?? sinEncaje.find((f) => f.hijo === hijo)?.personaje ?? "";
        return (
          <div key={hijo} className={styles.filaFan}>
            <h3 className={styles.filaFanTitulo}>
              {[
                nombre,
                personaje && personajeLegible(personaje),
                `${productos.length} ${productos.length === 1 ? "producto" : "productos"}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </h3>
            <TarjetasFan lineas={productos} />
            <NotasSinEncaje filas={sinEncaje.filter((f) => f.hijo === hijo)} />
          </div>
        );
      })}
    </section>
  );
}

// El resto de lo que compra un hijo, en fotos chicas: es un vistazo, no la lista (esa
// esta abajo, por categoria). Con muchas se muestran las primeras y "+N".
const MAX_MINIATURAS = 10;
function MiniaturasHijo({ lineas }: { lineas: LineaKit[] }) {
  const vistas = lineas.slice(0, MAX_MINIATURAS);
  const resto = lineas.length - vistas.length;
  return (
    <ul className={styles.miniaturas}>
      {vistas.map((linea) => {
        const producto = linea.producto_elegido!;
        const Icono = ICONO_CATEGORIA[categoriaDeLinea(linea)];
        return (
          <li key={linea.item_id} className={styles.miniatura} title={producto.nombre}>
            {producto.imagen_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={producto.imagen_url} alt={producto.nombre} loading="lazy" />
            ) : (
              <span aria-label={producto.nombre} role="img">
                <Icono size={22} strokeWidth={1.8} aria-hidden="true" />
              </span>
            )}
          </li>
        );
      })}
      {resto > 0 && (
        <li className={`${styles.miniatura} ${styles.miniaturaMas}`}>
          <span className="cifra">+{resto}</span>
        </li>
      )}
    </ul>
  );
}

function TarjetasFan({ lineas, veces }: { lineas: LineaKit[]; veces?: Record<string, number> }) {
  if (lineas.length === 0) return null;
  return (
    <ul className={styles.tarjetasFan}>
      {lineas.map((linea) => {
        const producto = linea.producto_elegido!;
        const Icono = ICONO_CATEGORIA[categoriaDeLinea(linea)];
        return (
          <li key={linea.item_id} className={styles.tarjetaFan}>
            {producto.imagen_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img className={styles.fotoOpcion} src={producto.imagen_url} alt="" loading="lazy" />
            ) : (
              <span className={styles.fotoOpcion} aria-hidden="true">
                <Icono size={32} strokeWidth={1.8} />
              </span>
            )}
            <span className={styles.tarjetaFanNombre}>
              {producto.nombre}
              {(veces?.[producto.sku] ?? 1) > 1 && ` ×${veces![producto.sku]}`}
            </span>
            <span className={styles.tarjetaFanConcepto}>{linea.descripcion}</span>
          </li>
        );
      })}
    </ul>
  );
}

function NotasSinEncaje({ filas }: { filas: FilaSinEncaje[] }) {
  if (filas.length === 0) return null;
  return (
    <ul className={styles.notasSinEncaje}>
      {filas.map((f) => (
        <li key={`${f.hijo}-${f.concepto}`}>{notaSinEncaje(f)}</li>
      ))}
    </ul>
  );
}

// El hogar con 2+ hijos: una tarjeta por hijo (quien es, su total, sus productos con
// personaje y lo que le falta) y, debajo, una sola seccion de lo que comparten con la
// foto de cada producto. Es de lectura: los cambios viven en la lista por categoria.
function ResumenPorHijo({
  kit,
  resumen,
  nombresHijos,
  gradosHijos,
  pedidos,
}: {
  kit: Kit;
  resumen: ResumenHijo[];
  nombresHijos: Map<string, string>;
  gradosHijos: Map<string, string>;
  pedidos?: Record<string, string[]>;
}) {
  const [colapsados, setColapsados] = useState<Set<string>>(new Set());
  const alternar = (hijo: string) =>
    setColapsados((prev) => {
      const siguiente = new Set(prev);
      if (siguiente.has(hijo)) siguiente.delete(hijo);
      else siguiente.add(hijo);
      return siguiente;
    });
  // Los productos con el personaje que pidio cada hijo (solo trae algo en Fan).
  const conPersonaje = new Map<string, LineaKit[]>();
  for (const g of personajesPorHijo(kit.lineas, pedidos)) {
    conPersonaje.set(g.hijo, [...(conPersonaje.get(g.hijo) ?? []), ...g.lineas]);
  }
  const ahorroTotal = kit.consolidaciones.reduce((n, c) => n + (c.ahorro > 0 ? c.ahorro : 0), 0);

  return (
    <section className={styles.familia} aria-labelledby="titulo-familia">
      <h2 id="titulo-familia" className={styles.familiaTitulo}>
        El kit de cada hijo
      </h2>
      <div className={styles.hijos}>
        {resumen.map((r) => {
          const abierto = !colapsados.has(r.hijo);
          const fan = conPersonaje.get(r.hijo) ?? [];
          const idsFan = new Set(fan.map((l) => l.item_id));
          const otros = r.productos.filter((l) => !idsFan.has(l.item_id));
          const meta = [
            `${r.renglones} ${r.renglones === 1 ? "útil" : "útiles"} de su lista`,
            r.comparten > 0 ? `${r.comparten} ${r.comparten === 1 ? "compartido" : "compartidos"}` : null,
            r.aparte > 0 ? `${r.aparte} por fuera de Tukit` : null,
          ].filter(Boolean);
          return (
            <article key={r.hijo} className={styles.tarjetaHijo}>
              <button
                type="button"
                className={styles.cabezaHijo}
                aria-expanded={abierto}
                onClick={() => alternar(r.hijo)}
              >
                <span className={styles.inicialHijo} aria-hidden="true">
                  {r.nombre.trim().charAt(0).toUpperCase()}
                </span>
                <span className={styles.identidadHijo}>
                  <span className={styles.nombreHijo}>{r.nombre}</span>
                  <span className={styles.datosHijo}>
                    {[r.grado, r.personaje ? personajeLegible(r.personaje) : null].filter(Boolean).join(" · ")}
                  </span>
                </span>
                <span className={styles.totalHijo}>
                  <span className="cifra">{hayQueCobrar(r.total) ? formatearPesos(r.total) : "—"}</span>
                  <span className={styles.metaHijo}>{meta.join(" · ")}</span>
                </span>
                {abierto ? (
                  <ChevronUp size={18} aria-hidden="true" className={styles.chevronHijo} />
                ) : (
                  <ChevronDown size={18} aria-hidden="true" className={styles.chevronHijo} />
                )}
              </button>
              {abierto && (
                <div className={styles.cuerpoHijo}>
                  {fan.length > 0 && (
                    <>
                      <h3 className={styles.subtituloHijo}>
                        Con {r.personaje ? personajeLegible(r.personaje) : "su personaje"}
                      </h3>
                      <TarjetasFan lineas={fan} veces={r.veces} />
                    </>
                  )}
                  {otros.length > 0 && (
                    <>
                      <h3 className={styles.subtituloHijo}>
                        {fan.length > 0 ? "El resto de su lista" : "Su lista"}
                        {/* Fotos de los productos, no un conteo: dos renglones que se
                            resuelven con el mismo producto salen una vez, y eso cambia
                            entre kits aunque la lista sea la misma. */}
                      </h3>
                      <MiniaturasHijo lineas={otros} />
                    </>
                  )}
                  {r.productos.length === 0 && r.falta.length === 0 && (
                    <p className={styles.metaHijo}>
                      Nada de su lista se compra en Tukit: abajo está qué conseguir y dónde.
                    </p>
                  )}
                  {r.falta.length > 0 && (
                    <ul className={styles.faltaHijo} aria-label={`Lo que falta para ${r.nombre}`}>
                      {r.falta.map((aviso, i) => (
                        <li key={i}>
                          <CircleAlert size={15} aria-hidden="true" /> {aviso}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {kit.consolidaciones.length > 0 && (
        <div className={styles.compartido} aria-labelledby="titulo-compartido">
          <div className={styles.compartidoCabeza}>
            <h3 id="titulo-compartido">Lo que comparten</h3>
            <p>
              Son iguales para varios de tus hijos: los compramos juntos y sobra menos.
              {ahorroTotal > 0 && (
                <>
                  {" "}
                  <strong className={styles.ahorroJunto}>Ahorras {formatearPesos(ahorroTotal)}.</strong>
                </>
              )}
            </p>
          </div>
          <ul className={styles.compartidoLista}>
            {kit.consolidaciones.map((c, i) => {
              const t = textoDeConsolidacion(c, nombresHijos, c.ahorro > 0 ? formatearPesos(c.ahorro) : null, gradosHijos);
              const { imagen_url, linea } = fotoDeConsolidacion(kit.lineas, c);
              const Icono = linea ? ICONO_CATEGORIA[categoriaDeLinea(linea)] : CircleAlert;
              return (
                <li key={`${c.producto}-${i}`} className={styles.compartidoItem}>
                  {imagen_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img className={styles.compartidoFoto} src={imagen_url} alt="" loading="lazy" />
                  ) : (
                    <span className={styles.compartidoFoto} aria-hidden="true">
                      <Icono size={26} strokeWidth={1.8} />
                    </span>
                  )}
                  <span className={styles.compartidoTexto}>
                    <strong>{c.producto}</strong>
                    <span>{[t.paraQuienes, t.cantidad].filter(Boolean).join(" · ")}</span>
                  </span>
                  {t.ahorro && <span className={`${styles.compartidoAhorro} cifra`}>−{formatearPesos(c.ahorro)}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}


// Lo que el acudiente compra va primero y completo. Todo lo que no se cobra en
// Tukit (libros, uniformes, licencias, lo que ya tiene en casa, lo que gestiona
// el colegio) va despues en un solo bloque compacto, agrupado por que hacer con
// ello: renglones cortos, sin tarjetas vacias ni la misma frase repetida.
// Lo que Tukit no supo resolver (huecos, sin leer, en revision) no se esconde:
// sale arriba con color de aviso, porque descubrirlo tarde es el dolor que la
// encuesta mas reporta.

const ABSTENCIONES: readonly ClaseLinea[] = ["hueco", "sin_match", "pendiente_revision"];

type GrupoFuera = { clave: string; titulo: string; Icono: LucideIcon; lineas: LineaKit[] };

function gruposFueraDelCarrito(lineas: readonly LineaKit[]): GrupoFuera[] {
  const libros: LineaKit[] = [];
  const uniformes: LineaKit[] = [];
  const colegio: LineaKit[] = [];
  const casa: LineaKit[] = [];
  const cuenta: LineaKit[] = [];
  for (const l of lineas) {
    const clase = clasificar(l);
    if (clase === "comprable" || ABSTENCIONES.includes(clase)) continue;
    if (esLibro(l)) libros.push(l);
    else if (esUniforme(l) || clase === "fuera_de_alcance") uniformes.push(l);
    else if (clase === "no_comprar") casa.push(l);
    else if (clase === "por_su_cuenta") cuenta.push(l);
    else colegio.push(l); // licencia_digital, informativa, diferido
  }
  return [
    { clave: "libros", titulo: "Libros", Icono: BookOpen, lineas: libros },
    { clave: "colegio", titulo: "Los pide o los vende el colegio", Icono: School, lineas: colegio },
    { clave: "uniformes", titulo: "Uniformes", Icono: Shirt, lineas: uniformes },
    { clave: "cuenta", titulo: "Consíguelos por tu cuenta", Icono: ShoppingBag, lineas: cuenta },
    { clave: "casa", titulo: "Usa el que ya tienes en casa", Icono: House, lineas: casa },
  ].filter((g) => g.lineas.length > 0);
}

function RenglonFuera({ linea, nombreHijo }: { linea: LineaKit; nombreHijo?: string }) {
  const producto = linea.producto_elegido;
  const donde = dondeComprar(linea);
  const razon = razonDeNoCobrar(linea);
  const precio = estadoDePrecio(linea);
  const detalle = [donde, linea.edicion?.titulo ? `edición ${linea.edicion.titulo}` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <li className={styles.renglonFuera}>
      {producto?.imagen_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img className={styles.fotoFuera} src={producto.imagen_url} alt="" loading="lazy" />
      )}
      <div className={styles.textoFuera}>
        <p className={styles.nombreFuera}>
          {linea.descripcion}
          {nombreHijo && <span className={styles.hijo}>{nombreHijo}</span>}
        </p>
        {(detalle || razon) && (
          <p className={styles.notaFuera}>
            {detalle || (precio.tipo === "sin_cobro" ? precio.titulo : razon)}
          </p>
        )}
      </div>
      {linea.url_externa && (
        <a className={styles.enlaceFuera} href={linea.url_externa} target="_blank" rel="noopener noreferrer">
          Cómo comprarlo <ExternalLink size={14} aria-hidden="true" />
        </a>
      )}
    </li>
  );
}

function SeccionesDeLineas({
  kit,
  trabajoId,
  nombresHijos,
}: {
  kit: Kit;
  trabajoId: string;
  nombresHijos: Map<string, string>;
}) {
  const abstenciones = kit.lineas.filter((l) => ABSTENCIONES.includes(clasificar(l)));
  // En el carrito, lo que el acudiente quito queda al final para que la lista
  // de lo que si se compra se lea seguida.
  const carrito = kit.lineas
    .filter((l) => clasificar(l) === "comprable")
    .sort((a, b) => Number(a.descartado === true) - Number(b.descartado === true));
  const enCarrito = carrito.filter((l) => !l.descartado).length;
  const fuera = gruposFueraDelCarrito(kit.lineas);
  const totalFuera = fuera.reduce((n, g) => n + g.lineas.length, 0);

  const renglon = (linea: LineaKit) => (
    <LineaDeKit
      key={linea.item_id}
      linea={linea}
      clase={clasificar(linea)}
      nombreHijo={linea.hijo ? nombresHijos.get(linea.hijo) : undefined}
      trabajoId={trabajoId}
      perfil={kit.perfil}
    />
  );

  return (
    <div className={styles.secciones}>
      {abstenciones.length > 0 && (
        <section className={`${styles.seccion} ${styles.seccion_hueco}`}>
          <header className={styles.cabeceraSeccion}>
            <h2>
              <CircleAlert size={20} aria-hidden="true" /> Revisa estos{" "}
              <span className={`${styles.conteo} cifra`}>{abstenciones.length}</span>
            </h2>
            <p>
              No los pudimos resolver y preferimos decírtelo a ofrecerte algo parecido como si fuera
              lo mismo.
            </p>
          </header>
          <ul className={styles.lineas}>{abstenciones.map(renglon)}</ul>
        </section>
      )}

      {carrito.length > 0 && (
        <section className={styles.seccion}>
          <header className={styles.cabeceraSeccion}>
            <h2>
              En tu carrito <span className={`${styles.conteo} cifra`}>{enCarrito}</span>
            </h2>
            <p>Puedes cambiar cualquier producto por otra opción o quitar lo que ya tienes.</p>
          </header>
          {agruparPorCategoria(carrito).map((grupo) => (
            <section
              key={grupo.categoria}
              id={idAnclaCategoria(grupo.categoria)}
              className={styles.grupoCategoria}
              data-categoria={grupo.categoria}
              aria-labelledby={`${idAnclaCategoria(grupo.categoria)}-titulo`}
            >
              <CabeceraCategoria
                titulo={grupo.titulo}
                categoria={grupo.categoria}
                lineas={grupo.lineas}
                trabajoId={trabajoId}
                perfil={kit.perfil}
              />
              <ul className={styles.lineas}>{grupo.lineas.map(renglon)}</ul>
            </section>
          ))}
        </section>
      )}

      {totalFuera > 0 && (
        <section className={`${styles.seccion} ${styles.fueraCarrito}`}>
          <header className={styles.cabeceraSeccion}>
            <h2>
              Fuera del carrito <span className={`${styles.conteo} cifra`}>{totalFuera}</span>
            </h2>
            <p>
              También están en la lista, pero no se compran en Tukit. Te decimos qué hacer con cada
              uno; no suman al total.
            </p>
          </header>
          {fuera.map(({ clave, titulo, Icono, lineas }) => (
            <div key={clave} className={styles.grupoFuera}>
              <h3>
                <Icono size={16} aria-hidden="true" /> {titulo}
              </h3>
              <ul>
                {lineas.map((l) => (
                  <RenglonFuera
                    key={l.item_id}
                    linea={l}
                    nombreHijo={l.hijo ? nombresHijos.get(l.hijo) : undefined}
                  />
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
