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
  ExternalLink,
  House,
  School,
  ShoppingBag,
  type LucideIcon,
} from "lucide-react";
import { prefiereMenosMovimiento } from "@tukit/contrato/motion";
import {
  agruparPorClase,
  clasificar,
  dondeComprar,
  esBogota,
  esLibro,
  esUniforme,
  estadoDePrecio,
  formatearPesos,
  hayQueCobrar,
  LOCALIDADES_BOGOTA,
  personajesDelKit,
  productosDelPersonaje,
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
import { etiquetasDeHijos, textoDeConsolidacion, type ApodoMatricula } from "@/lib/kit-vista";
import { abrirWidgetWompi } from "@/lib/wompi";
import CampoDireccion, { type LugarElegido } from "./CampoDireccion";
import CampoDireccionOsm from "./CampoDireccionOsm";
import LineaDeKit from "./LineaDeKit";
import AsistenteKitSlot from "./AsistenteKitSlot";
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

export default function VistaKits({
  trabajo,
  correo,
  llaveMaps,
  matriculas,
  entregaPrevia,
  abrirPago,
}: {
  trabajo: Trabajo;
  correo: string;
  llaveMaps: string | null;
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

      {kit.perfil === "Fan" && <FranjaFan lineas={kit.lineas} />}

      {kit.consolidaciones.length > 0 && (
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
              );
              return (
                <li key={`${c.producto}-${i}`}>
                  <strong>{c.producto}</strong>
                  <span>
                    {[t.paraQuienes, t.cantidad].filter(Boolean).join(" · ")}
                  </span>
                  {t.ahorro && <span className={styles.ahorroJunto}>{t.ahorro}</span>}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <SeccionesDeLineas kit={kit} trabajoId={trabajo.trabajo_id} nombresHijos={nombresHijos} />

      <AsistenteKitSlot trabajoId={trabajo.trabajo_id} perfil={kit.perfil} />

      <Checkout
        trabajoId={trabajo.trabajo_id}
        perfil={kit.perfil}
        total={kit.total}
        correo={correo}
        llaveMaps={llaveMaps}
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
  llaveMaps,
  entregaPrevia,
  abrirPago,
}: {
  trabajoId: string;
  perfil: PerfilKit;
  total: number;
  correo: string;
  // La llave de Google Places, leida en el servidor; `null` => campos manuales.
  llaveMaps: string | null;
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
    ciudad: "",
    localidad: "",
    departamento: "",
    // Solo si la direccion salio de una sugerencia de Google y no se edito.
    google_place_id: "",
    // El pin confirmado en el mapa de OpenStreetMap (sin llave de Google).
    latitud: null as number | null,
    longitud: null as number | null,
    // Tras un pago rechazado, la entrega que ya se habia escrito.
    ...entregaPrevia,
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
      latitud: lugar.latitud ?? null,
      longitud: lugar.longitud ?? null,
      ciudad: lugar.ciudad || d.ciudad,
      localidad: lugar.localidad,
      departamento: lugar.departamento || d.departamento,
    }));

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
        localidad: enBogota ? datos.localidad : "",
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
          {/* Con llave de Google, sus sugerencias (ADR 0044). Sin llave, la
              búsqueda en OpenStreetMap con mapa de confirmación (ADR 0049). */}
          {llaveMaps ? (
            <CampoDireccion
              llave={llaveMaps}
              valor={datos.direccion}
              onEscribir={escribirDireccion}
              onElegir={elegirLugar}
            />
          ) : (
            <CampoDireccionOsm
              valor={datos.direccion}
              latitud={datos.latitud}
              longitud={datos.longitud}
              onEscribir={escribirDireccion}
              onElegir={elegirLugar}
              onMoverPin={moverPin}
            />
          )}
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

function FranjaFan({ lineas }: { lineas: LineaKit[] }) {
  const productos = productosDelPersonaje(lineas);
  if (productos.length === 0) return null;
  const personajes = personajesDelKit(lineas);
  return (
    <section className={styles.franjaFan} aria-labelledby="titulo-franja-fan">
      <h2 id="titulo-franja-fan">
        {personajes.length === 1 ? `Tu kit de ${personajes[0]}` : "Tu kit con personajes"}
      </h2>
      <p>
        Por esto es el kit Fan: {productos.length}{" "}
        {productos.length === 1 ? "producto" : "productos"} con el personaje que pidió tu hijo.
        Abajo está la lista completa.
      </p>
      <ul className={styles.tarjetasFan}>
        {productos.map((linea) => {
          const producto = linea.producto_elegido!;
          return (
            <li key={producto.sku} className={styles.tarjetaFan}>
              {producto.imagen_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img className={styles.fotoOpcion} src={producto.imagen_url} alt="" loading="lazy" />
              ) : (
                <span className={styles.fotoOpcion} aria-hidden="true">
                  sin foto
                </span>
              )}
              <span className={styles.tarjetaFanNombre}>{producto.nombre}</span>
              <span className={styles.tarjetaFanConcepto}>{linea.descripcion}</span>
            </li>
          );
        })}
      </ul>
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
          <ul className={styles.lineas}>{carrito.map(renglon)}</ul>
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
