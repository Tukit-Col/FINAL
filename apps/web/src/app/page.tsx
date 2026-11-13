import Image from "next/image";
import Link from "next/link";
import {
  Sparkles,
  Route,
  PackageSearch,
  BookMarked,
  ShoppingBasket,
  Cpu,
  ShieldCheck,
  Eye,
  ArrowRight,
  PackageCheck,
} from "lucide-react";
import Revelar from "@/components/Revelar";
import UtilesFlotantes from "./UtilesFlotantes";
import LineaDelTiempo from "./LineaDelTiempo";
import { Foco, Marcador, Palabras, Contador, Paralaje } from "./MovimientoInicio";
import styles from "./Inicio.module.css";

export const dynamic = "force-dynamic";

// Marco de copy (Julian Shapiro): la portada abre con el DOLOR del acudiente,
// no con el catálogo ni con el precio. Los útiles distintos, las tiendas y los
// productos curados son cifras del backend que a un papá no le dicen nada: no
// van en el héroe. Lo que sí va es la promesa —te lo resolvemos de verdad— y la
// razón por la que es creíble —una persona revisa, y lo que no hay te lo
// decimos—. El ahorro aparece tarde y en voz baja: en la encuesta fue el dolor
// que MENOS gente nombró, y liderar con descuentos sería contestar la pregunta
// que casi nadie hizo.

// Los dolores de la encuesta, ya sin el porcentaje: el número era ruido para
// quien llega a comprar. Cada tarjeta es un dolor real y, debajo, lo que
// hacemos con él —la promesa se gana objeción por objeción, no de una—.
const DOLORES = [
  {
    Icono: PackageSearch,
    titulo: "Recorrer papelerías y que esté agotado",
    respuesta:
      "Si no lo tenemos, te lo decimos con esas palabras. Nunca te ofrecemos algo parecido haciéndolo pasar por lo que pediste.",
  },
  {
    Icono: BookMarked,
    titulo: "Los libros y el plan lector nunca cuadran",
    respuesta:
      "Los textos se resuelven por edición, no por parecido. Y cuando el colegio los cierra a una editorial, te decimos cómo conseguirlos en vez de callarlo.",
  },
  {
    Icono: ShoppingBasket,
    titulo: "No encontrar todo en un solo lugar",
    respuesta:
      "Un solo pedido para todos tus hijos, con lo repetido junto: dos borradores sueltos cuestan más que una caja de diez.",
  },
];

// Por qué es creíble: las tres cosas que hacemos distinto, cada una responde una
// objeción que el acudiente ya trae puesta ("¿otra tienda que promete?"). La
// primera es la propuesta de valor: la IA hace en minutos lo que a ti te toma
// una tarde. La segunda dice que igual una persona lo revisa (la IA no manda
// sola). La tercera es la promesa de decir la verdad sobre lo que no hay.
const RAZONES = [
  {
    Icono: Cpu,
    titulo: "Una IA arma el kit en minutos",
    texto:
      "Lee tu lista renglón por renglón y busca cada útil en las tiendas que sí lo tienen. Lo que a ti te cuesta una tarde de papelería, aquí toma minutos.",
  },
  {
    Icono: ShieldCheck,
    titulo: "Y una persona lo revisa",
    texto:
      "La IA propone, pero no manda sola. Antes de que veas tu kit, alguien del equipo revisa lo que quedó dudoso. Rápido no significa a la carrera.",
  },
  {
    Icono: Eye,
    titulo: "Te decimos lo que no tenemos",
    texto:
      "Un catálogo que solo cuenta lo que sí tiene es el que te hace perder la tarde. Nosotros publicamos también lo que todavía nos falta.",
  },
];

// Las tres etapas visibles del servicio, cada una con su foto. El detalle de
// siete pasos (quién hace qué) queda debajo, en la línea del tiempo.
const ETAPAS_FOTO = [
  {
    n: "1",
    titulo: "Armas",
    texto: "Eliges colegio y grado, o subes la lista. Una IA la lee y te arma tres kits.",
    src: "/marca/caja-abierta-hero.webp",
    alt: "Caja Tukit abierta sobre una mesa con cuadernos, lápices de colores, tijeras y colbón ordenados por compartimentos",
    zoom: true,
  },
  {
    n: "2",
    titulo: "Preparamos",
    texto: "Una persona del equipo revisa lo dudoso y alista la caja con cada útil en su lugar.",
    src: "/marca/preparando-la-caja.webp",
    alt: "Una persona acomoda cuadernos, marcadores y lápices dentro de una caja blanca sobre una mesa de madera",
    zoom: false,
  },
  {
    n: "3",
    titulo: "Llega a tu puerta",
    texto: "Un solo pedido para todos tus hijos, en una caja Tukit frente a tu casa.",
    src: "/marca/llega-a-tu-puerta.webp",
    alt: "Caja Tukit Premium cerrada, entregada frente a la puerta de una casa",
    zoom: false,
  },
];

// Cifras que sí son nuestras y verificables: la encuesta y el diseño del servicio.
const CIFRAS = [
  { valor: 60, sufijo: "", texto: "acudientes nos contaron su tarde de papelería" },
  { valor: 3, sufijo: "", texto: "kits por lista, para que decidas tú" },
  { valor: 1, sufijo: "", texto: "solo pedido por hogar, con todos tus hijos" },
];

export default async function Inicio() {
  return (
    <div className={styles.pagina}>
      {/* Útiles esparcidos por toda la página (fondo), para que el scroll entre
          secciones no se sienta vacío. Decorativos. */}
      <UtilesFlotantes variante="pagina" />

      <section className={styles.heroe}>
        {/* Útiles en clay flotando alrededor del titular. Decorativos. */}
        <UtilesFlotantes />

        <Revelar className={styles.heroeTexto} modo="cascada" cadaUno={0.1}>
          <p className={styles.antetitulo}>
            <Sparkles size={14} aria-hidden="true" strokeWidth={2.6} />
            Listas escolares, resueltas
          </p>
          {/* Header con la propuesta de valor directa: el acento va bajo lo que
              de verdad compras, que no son útiles sino la tarde de vuelta. */}
          <h1 className={styles.titular}>
            Menos filas,
            <br />
            más <em>tiempo en familia.</em>
          </h1>
          {/* Subheader: qué es + por qué es posible (la IA), en dos frases. */}
          <p className={styles.bajada}>
            Nos dices de qué colegio y grado es la lista, o le tomas una foto, y una IA te
            arma tres kits con todo lo de tus hijos en un solo pedido. Antes de que lo veas,
            una persona lo revisa, para que llegue seguro a tu casa.
          </p>

          <div className={styles.acciones}>
            <Link href="/empezar" className={styles.botonPrimario}>
              <Sparkles size={18} aria-hidden="true" strokeWidth={2.6} />
              Armar mi kit
            </Link>
            <Link href="/#como-funciona" className={styles.botonSecundario}>
              <Route size={18} aria-hidden="true" strokeWidth={2.4} />
              Ver cómo funciona
            </Link>
          </div>

          {/* Micro-prueba bajo los CTA: baja el esfuerzo percibido antes del clic. */}
          <p className={styles.tranquilizador}>
            Armar el kit no cuesta nada · Tú eliges entre tres · Sin crear cuenta para empezar
          </p>
        </Revelar>

        {/* Foto del heroe: la caja abierta, lo que de verdad llega. Es la
            unica imagen con `priority` (esta sobre el pliegue en escritorio). */}
        <Paralaje className={styles.heroeFoto}>
          <Image
            src="/marca/caja-abierta-hero.webp"
            alt="Caja Tukit abierta sobre una mesa, con cuadernos, lápices de colores, tijeras y colbón ordenados por compartimentos, y una caja Premium al lado"
            fill
            priority
            sizes="(max-width: 1120px) 100vw, 1000px"
            className={styles.heroeImagen}
          />
        </Paralaje>
        <p className={styles.sello}>
          <PackageCheck size={16} aria-hidden="true" strokeWidth={2.4} />
          Revisado por una persona antes de salir
        </p>
      </section>

      <section className={styles.cifras} aria-label="Tukit en cifras">
        <Revelar as="ul" className={styles.rejillaCifras} modo="scroll" cadaUno={0.1}>
          {CIFRAS.map(({ valor, sufijo, texto }) => (
            <li key={texto} className={styles.cifra}>
              <strong>
                <Contador valor={valor} sufijo={sufijo} />
              </strong>
              <span>{texto}</span>
            </li>
          ))}
        </Revelar>
      </section>

      <section className={styles.dolores} aria-labelledby="titulo-dolores">
        <Revelar className={styles.encabezadoSeccion} modo="una">
          <p className={styles.kicker}>Lo que nos dijeron 60 acudientes</p>
          <h2 id="titulo-dolores" className={styles.tituloSeccion}>
            Sabemos por qué la lista del colegio se vuelve una <Marcador>tarde perdida</Marcador>
          </h2>
          <p className={styles.subtituloSeccion}>
            Preguntamos qué era lo que más pesaba. No inventamos el problema: lo oímos, y
            armamos el servicio alrededor de él.
          </p>
        </Revelar>
        <Revelar as="ul" className={styles.rejillaDolores} modo="scroll" cadaUno={0.08}>
          {DOLORES.map(({ Icono, titulo, respuesta }) => (
            <Foco as="li" key={titulo} className={styles.dolor}>
              <span className={styles.dolorIcono} aria-hidden="true">
                <Icono size={22} strokeWidth={2.2} />
              </span>
              <h3>{titulo}</h3>
              <p>{respuesta}</p>
            </Foco>
          ))}
        </Revelar>
      </section>

      <section className={styles.razones} aria-labelledby="titulo-razones">
        <Revelar className={styles.encabezadoSeccion} modo="una">
          <p className={styles.kicker}>Por qué puedes confiar</p>
          <h2 id="titulo-razones" className={styles.tituloSeccion}>
            No es otra tienda que promete y desaparece
          </h2>
        </Revelar>
        <Revelar as="ul" className={styles.rejillaRazones} modo="scroll" cadaUno={0.08}>
          {RAZONES.map(({ Icono, titulo, texto }) => (
            <Foco as="li" key={titulo} className={styles.razon}>
              <span className={styles.razonIcono} aria-hidden="true">
                <Icono size={22} strokeWidth={2.2} />
              </span>
              <h3>{titulo}</h3>
              <p>{texto}</p>
            </Foco>
          ))}
        </Revelar>
      </section>

      <section id="como-funciona" className={styles.comoFunciona} aria-labelledby="titulo-como">
        <Revelar className={styles.encabezadoSeccion} modo="una">
          <p className={styles.kicker}>De la lista a tu casa</p>
          <h2 id="titulo-como" className={styles.tituloSeccion}>
            Así de simple: armas, preparamos, llega
          </h2>
        </Revelar>
        <Revelar as="ol" className={styles.pasosFoto} modo="scroll" cadaUno={0.14}>
          {ETAPAS_FOTO.map(({ n, titulo, texto, src, alt, zoom }, i) => (
            <Foco as="li" key={n} className={styles.pasoFoto}>
              <div className={styles.pasoImagen}>
                <Image
                  src={src}
                  alt={alt}
                  fill
                  sizes="(max-width: 760px) 92vw, 360px"
                  className={zoom ? styles.pasoZoom : undefined}
                />
                <span className={styles.pasoNumero} aria-hidden="true">
                  {n}
                </span>
              </div>
              <div className={styles.pasoCuerpo}>
                <h3>{titulo}</h3>
                <p>{texto}</p>
              </div>
              {i < ETAPAS_FOTO.length - 1 && (
                <ArrowRight className={styles.pasoFlecha} size={22} aria-hidden="true" strokeWidth={2.6} />
              )}
            </Foco>
          ))}
        </Revelar>

        <Revelar className={styles.detalle} modo="una">
          <h3 className={styles.detalleTitulo}>Y el detalle, paso a paso</h3>
          <p className={styles.subtituloSeccion}>
            Siete pasos, y en cada uno decimos quién lo hace: tú, la IA, o una persona del
            equipo que revisa. El último todavía lo estamos construyendo, y lo decimos aquí
            en vez de prometerlo antes de tiempo.
          </p>
        </Revelar>
        <LineaDelTiempo />
      </section>

      <section className={styles.cierre} aria-labelledby="titulo-cierre">
        <div className={styles.tarjetaCierre}>
          {/* Reparto liviano de útiles en las esquinas para que la tarjeta no se
              sienta vacía. Decorativo. */}
          <UtilesFlotantes variante="cierre" />
          <Revelar className={styles.cierreTexto} modo="una">
            <h2 id="titulo-cierre" className={styles.tituloCierre}>
              <Palabras texto="Esa tarde de papelería, esta vez pásala en casa." />
            </h2>
            <p className={styles.bajadaCierre}>
              Toma un minuto. Armas el kit, ves los tres precios y decides sin compromiso.
            </p>
            <Link href="/empezar" className={styles.botonPrimario}>
              <Sparkles size={18} aria-hidden="true" strokeWidth={2.6} />
              Armar mi kit
            </Link>
          </Revelar>
        </div>
      </section>
    </div>
  );
}
