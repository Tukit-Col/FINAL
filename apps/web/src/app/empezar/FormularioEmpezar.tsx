"use client";

import { useCallback, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Check, School, Pencil } from "lucide-react";
import {
  formatearTamano,
  validarArchivo,
  EXTENSIONES_ACEPTADAS,
  GRADOS_CANONICOS,
  type Colegio,
  type GradoCanonico,
  type HijoSolicitud,
  type PerfilKit,
  type Pesos,
  type SolicitudTrabajo,
} from "@tukit/contrato";
import { aplicarCanonico, crearTrabajo, subirListas, FalloApi } from "@/lib/api-navegador";
import SelectorPersonaje from "./SelectorPersonaje";
import styles from "./Empezar.module.css";

type Entrada = "lista_oficial" | "archivo";

interface HijoFormulario {
  referencia: string;
  // La ruta "lista oficial" elige un colegio ALIADO por su id. La ruta "subir
  // archivo" designa el colegio de otra forma (no es aliado todavía): con el
  // DANE del directorio de Bogotá, o solo con el nombre escrito a mano. El
  // backend deriva el `colegio_id` estable de lo que llegue; aquí se guardan las
  // tres piezas y se manda la que corresponda según la ruta.
  colegioId: string;
  colegioDane: string;
  colegioNombre: string;
  grado: string;
  entrada: Entrada;
  archivo: File | null;
  errorArchivo: string | null;
  personajes: string;
}

// El paso 3 no es una encuesta socioeconómica: es la ÚNICA palanca del
// acudiente sobre cuál de los tres kits le marcamos. Por eso pregunta lo que el
// recomendador de verdad lee —los pesos y la disposición a pagar de más
// (`optimizador.recomendar`)— y no un "dolor" que no movía nada.
//
// El encuadre es cuánto gastar, NO precio contra calidad: la calidad asegurada
// está en los tres kits, lo que cambia es la economía. Tres opciones, cada una
// con su efecto declarado en pantalla:
//   • "Lo más económico" -> Ahorrador (el gasto manda, sin sobreprecio)
//   • "Un punto medio"   -> Ahorrador por defecto de la encuesta (P21)
//   • "Puedo estirarme"  -> Premium, si acepta pagar un poco más
// El Fan no vive aquí: se dispara solo si en el paso 1 pediste un personaje.
type ClavePrioridad = "precio" | "equilibrio" | "calidad";

interface Prioridad {
  clave: ClavePrioridad;
  titulo: string;
  detalle: string;
  // Lo que se manda al backend: los pesos suman 1.0 (el §3 lo exige, y el
  // validador de inteligencia devuelve 422 si no) y la disposición a pagar de
  // más, que es lo que destraba el Premium.
  pesos: Pesos;
  disposicion_sobreprecio: number;
}

const PRIORIDADES: Prioridad[] = [
  {
    clave: "precio",
    titulo: "Lo más económico",
    detalle: "Gastar lo menos posible. Te marcamos el Ahorrador.",
    pesos: { precio: 0.6, marca_exigida: 0.15, calidad: 0.2, personaje: 0.05 },
    disposicion_sobreprecio: 0,
  },
  {
    clave: "equilibrio",
    titulo: "Un punto medio",
    detalle: "Sin gastar de más, pero con algo de marca. Te marcamos el Ahorrador y dejamos los otros dos a la vista.",
    pesos: { precio: 0.35, marca_exigida: 0.3, calidad: 0.25, personaje: 0.1 },
    disposicion_sobreprecio: 0.05,
  },
  {
    clave: "calidad",
    titulo: "Puedo estirarme un poco",
    detalle: "Marcas y acabados de gama alta. Te marcamos el Premium si cabe en tu tope.",
    pesos: { precio: 0.15, marca_exigida: 0.35, calidad: 0.4, personaje: 0.1 },
    disposicion_sobreprecio: 0.1,
  },
];

// La ruta rapida no manda pesos: manda UN kit ya validado. El paso 3 (economia)
// y el personaje del paso 1 se colapsan al perfil que se aplica. Decision del
// usuario: personaje gana -> Fan; si no, precio/equilibrio -> Ahorrador,
// calidad -> Premium.
function perfilDeSeleccion(prioridad: ClavePrioridad, tienePersonaje: boolean): PerfilKit {
  if (tienePersonaje) return "Fan";
  return prioridad === "calidad" ? "Premium" : "Ahorrador";
}

function hijoVacio(indice: number): HijoFormulario {
  return {
    referencia: `hijo-${indice}`,
    colegioId: "",
    colegioDane: "",
    colegioNombre: "",
    grado: "",
    entrada: "lista_oficial",
    archivo: null,
    errorArchivo: null,
    personajes: "",
  };
}

// Iniciales del colegio para el avatar cuando no hay logo: dos letras de las
// dos primeras palabras significativas, en mayúscula.
function iniciales(nombre: string): string {
  const palabras = nombre
    .split(/\s+/)
    .filter((p) => p.length > 2 && !/^(de|del|la|el|los|las|y)$/i.test(p));
  const base = palabras.length > 0 ? palabras : nombre.split(/\s+/);
  return base
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

// ------------------------------------------------------- Selector de colegio

function SelectorColegio({
  colegios,
  valor,
  onElegir,
}: {
  colegios: Colegio[];
  valor: string;
  onElegir: (colegioId: string) => void;
}) {
  const [busqueda, setBusqueda] = useState("");
  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return colegios;
    return colegios.filter((c) => c.nombre.toLowerCase().includes(q));
  }, [colegios, busqueda]);

  return (
    <div className={styles.colegioBloque}>
      <span className={styles.campoRotulo}>Colegio</span>
      <div className={styles.buscador}>
        <Search size={16} strokeWidth={2.4} aria-hidden="true" />
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Busca tu colegio…"
          aria-label="Buscar colegio"
        />
      </div>
      <div className={styles.listaColegios} role="radiogroup" aria-label="Elige el colegio">
        {filtrados.map((c) => {
          const activo = c.colegio_id === valor;
          return (
            <button
              key={c.colegio_id}
              type="button"
              role="radio"
              aria-checked={activo}
              className={`${styles.tarjetaColegio} ${activo ? styles.colegioActivo : ""}`}
              onClick={() => onElegir(c.colegio_id)}
            >
              <span className={styles.logoColegio} aria-hidden="true">
                {c.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.logo_url} alt="" />
                ) : (
                  <span className={styles.logoIniciales}>{iniciales(c.nombre)}</span>
                )}
              </span>
              <span className={styles.colegioTexto}>
                <span className={styles.colegioNombre}>{c.nombre}</span>
                <span className={styles.colegioMeta}>
                  {c.grados.length === 0
                    ? "Sin lista verificada · sube el archivo"
                    : `${c.grados.length} ${c.grados.length === 1 ? "grado verificado" : "grados verificados"}`}
                </span>
              </span>
              {activo && (
                <span className={styles.colegioMarca} aria-hidden="true">
                  <Check size={14} strokeWidth={3.2} />
                </span>
              )}
            </button>
          );
        })}
        {filtrados.length === 0 && (
          <p className={styles.sinColegios}>
            <School size={18} strokeWidth={2} aria-hidden="true" />
            No encontramos ese colegio entre los aliados todavía.
          </p>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------ Buscador del directorio de Bogotá
//
// Una entrada del directorio estático de colegios de Bogotá
// (`/directorio-colegios.json`, ~3k colegios). NO es un colegio aliado: es la
// guía oficial para que el acudiente designe SU colegio al subir el archivo,
// aunque Tukit todavía no lo tenga. La búsqueda es del lado del cliente sobre el
// JSON ya cargado; no pega a ningún servicio (decisión: directorio buscable, no
// sembrado).
interface EntradaDirectorio {
  dane: string;
  nombre: string;
  localidad: string;
}

// El directorio se carga UNA vez y se comparte entre todos los hijos: es el
// mismo JSON estático. Se memoiza en un módulo para no re-descargar 300 KB por
// cada `<BuscadorDirectorio>` que se monte.
let directorioPromesa: Promise<EntradaDirectorio[]> | null = null;
function cargarDirectorio(): Promise<EntradaDirectorio[]> {
  if (!directorioPromesa) {
    directorioPromesa = fetch("/directorio-colegios.json")
      .then((r) => (r.ok ? (r.json() as Promise<EntradaDirectorio[]>) : []))
      .catch(() => []);
  }
  return directorioPromesa;
}

function BuscadorDirectorio({
  dane,
  nombre,
  onElegir,
  onEscribir,
}: {
  dane: string;
  nombre: string;
  // Eligió una entrada del directorio: viaja el DANE (deriva el id) y el nombre.
  onElegir: (entrada: { dane: string; nombre: string }) => void;
  // Lo escribió a mano porque no está en el directorio: solo el nombre.
  onEscribir: (nombre: string) => void;
}) {
  const [directorio, setDirectorio] = useState<EntradaDirectorio[]>([]);
  const [busqueda, setBusqueda] = useState("");
  // Cargar el directorio al primer foco/tecleo, no al montar: la mayoría de los
  // hogares usa la lista aliada y nunca abre esta ruta.
  const asegurarCargado = useCallback(() => {
    if (directorio.length === 0) cargarDirectorio().then(setDirectorio);
  }, [directorio.length]);

  const q = busqueda.trim().toLowerCase();
  const resultados = useMemo(() => {
    if (q.length < 3) return [];
    return directorio.filter((e) => e.nombre.toLowerCase().includes(q)).slice(0, 30);
  }, [directorio, q]);

  // Ya eligió (por directorio o a mano): se muestra el elegido con opción de
  // cambiarlo, en vez de la lista, para que el paso quede claramente resuelto.
  if (nombre) {
    return (
      <div className={styles.colegioBloque}>
        <span className={styles.campoRotulo}>Colegio</span>
        <div className={`${styles.tarjetaColegio} ${styles.colegioActivo}`}>
          <span className={styles.logoColegio} aria-hidden="true">
            <span className={styles.logoIniciales}>{iniciales(nombre)}</span>
          </span>
          <span className={styles.colegioTexto}>
            <span className={styles.colegioNombre}>{nombre}</span>
            <span className={styles.colegioMeta}>
              {dane ? `Directorio de Bogotá · DANE ${dane}` : "Escrito a mano · lo verificamos nosotros"}
            </span>
          </span>
          <button
            type="button"
            className={styles.cambiarColegio}
            onClick={() => {
              onEscribir("");
              setBusqueda("");
            }}
          >
            Cambiar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.colegioBloque}>
      <span className={styles.campoRotulo}>Colegio</span>
      <div className={styles.buscador}>
        <Search size={16} strokeWidth={2.4} aria-hidden="true" />
        <input
          type="text"
          value={busqueda}
          onFocus={asegurarCargado}
          onChange={(e) => {
            asegurarCargado();
            setBusqueda(e.target.value);
          }}
          placeholder="Busca tu colegio en el directorio de Bogotá…"
          aria-label="Buscar colegio en el directorio de Bogotá"
        />
      </div>
      {q.length >= 3 && (
        <div className={styles.listaColegios} role="listbox" aria-label="Colegios del directorio">
          {resultados.map((e) => (
            <button
              key={`${e.dane}`}
              type="button"
              role="option"
              aria-selected="false"
              className={styles.tarjetaColegio}
              onClick={() => onElegir({ dane: e.dane, nombre: e.nombre })}
            >
              <span className={styles.logoColegio} aria-hidden="true">
                <span className={styles.logoIniciales}>{iniciales(e.nombre)}</span>
              </span>
              <span className={styles.colegioTexto}>
                <span className={styles.colegioNombre}>{e.nombre}</span>
                <span className={styles.colegioMeta}>{e.localidad}</span>
              </span>
            </button>
          ))}
          {/* No está en el directorio: se escribe a mano. El backend deriva el
              id del nombre normalizado, así que dos acudientes que escriban el
              mismo colegio convergen a la misma versión. */}
          <button
            type="button"
            className={styles.escribirColegio}
            onClick={() => onEscribir(busqueda.trim())}
          >
            <Pencil size={15} strokeWidth={2.4} aria-hidden="true" />
            No lo encuentro: usar “{busqueda.trim()}” tal cual
          </button>
        </div>
      )}
      {q.length > 0 && q.length < 3 && (
        <p className={styles.sinColegios}>
          <School size={18} strokeWidth={2} aria-hidden="true" />
          Escribe al menos tres letras del nombre.
        </p>
      )}
    </div>
  );
}

export default function FormularioEmpezar({
  colegios,
  surtidos,
  canonicos,
}: {
  colegios: Colegio[];
  surtidos: string[];
  canonicos: GradoCanonico[];
}) {
  const router = useRouter();
  const idBase = useId();

  const [hijos, setHijos] = useState<HijoFormulario[]>([hijoVacio(1)]);
  const [correo, setCorreo] = useState("");
  const [celular, setCelular] = useState("");
  // Paso 1 · la cuenta. El nombre es el del ADULTO (PERSONAL, no de menor). La
  // clave crea cuentas reales desde el minuto uno; `yaTengoCuenta` alterna a
  // iniciar sesion; `sesionLista` marca que el paso 1 quedo resuelto (la cookie
  // ya la puso el Route Handler) y habilita armar el kit.
  const [nombre, setNombre] = useState("");
  const [clave, setClave] = useState("");
  const [yaTengoCuenta, setYaTengoCuenta] = useState(false);
  const [sesionLista, setSesionLista] = useState(false);
  const [resolviendoCuenta, setResolviendoCuenta] = useState(false);
  const [prioridad, setPrioridad] = useState<ClavePrioridad>("equilibrio");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gradosDetectados, setGradosDetectados] = useState<string[]>([]);

  const porId = useMemo(() => new Map(colegios.map((c) => [c.colegio_id, c])), [colegios]);

  function cambiar(indice: number, cambio: Partial<HijoFormulario>) {
    setHijos((actuales) =>
      actuales.map((hijo, i) => (i === indice ? { ...hijo, ...cambio } : hijo)),
    );
  }

  function elegirArchivo(indice: number, elegido: File | undefined) {
    if (!elegido) return;
    const problema = validarArchivo(elegido);
    cambiar(indice, {
      archivo: problema ? null : elegido,
      errorArchivo: problema,
    });
  }

  // Un hijo está completo según su ruta: la lista aliada necesita el `colegioId`;
  // la subida necesita el nombre del colegio (del directorio o a mano) y el
  // archivo. El grado siempre.
  const hijoListo = useCallback((hijo: HijoFormulario) => {
    if (!hijo.grado) return false;
    if (hijo.entrada === "lista_oficial") return Boolean(hijo.colegioId);
    return Boolean(hijo.colegioNombre) && hijo.archivo !== null;
  }, []);

  // El paso 1 (cuenta) tiene su propio gate: sin resolverlo no se puede enviar
  // el kit. Crear cuenta pide nombre + celular; iniciar sesion solo correo+clave.
  const cuentaCompletable =
    correo.trim().length > 3 &&
    clave.trim().length >= 8 &&
    (yaTengoCuenta || (nombre.trim().length > 0 && celular.trim().length > 6));

  const listo = sesionLista && hijos.every(hijoListo);

  // Resuelve el paso 1 contra el mismo backend que el login: crea la cuenta
  // (POST /empezar/api/cuenta) o inicia sesion (POST /api/sesion). En ambos
  // casos el Route Handler pone la cookie httpOnly; el formulario nunca ve el
  // token, solo marca `sesionLista`. Un correo ya registrado empuja a login.
  async function resolverCuenta() {
    if (!cuentaCompletable || resolviendoCuenta) return;
    setResolviendoCuenta(true);
    setError(null);

    const ruta = yaTengoCuenta ? "/api/sesion" : "/empezar/api/cuenta";
    const cuerpo = yaTengoCuenta
      ? { correo: correo.trim(), clave }
      : { correo: correo.trim(), clave, nombre: nombre.trim(), celular: celular.trim() };

    try {
      const respuesta = await fetch(ruta, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      });
      if (respuesta.ok) {
        setSesionLista(true);
        // Cookie de sesion recien puesta: invalidar la Router Cache para que la
        // cabecera (server component) reconozca al usuario sin recarga manual.
        router.refresh();
        return;
      }
      const detalle = (await respuesta.json().catch(() => ({}))) as { error?: string; mensaje?: string };
      if (detalle.error === "correo_ya_registrado") {
        setYaTengoCuenta(true);
        setError("Ese correo ya tiene cuenta — inicia sesión con tu clave.");
      } else if (respuesta.status === 401) {
        setError("Correo o clave incorrectos.");
      } else {
        setError(detalle.mensaje ?? "No pudimos con tu cuenta. Intenta de nuevo.");
      }
    } catch {
      setError("No pudimos con tu cuenta. Revisa tu conexión e intenta de nuevo.");
    } finally {
      setResolviendoCuenta(false);
    }
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!listo || enviando) return;
    setEnviando(true);
    setError(null);
    setGradosDetectados([]);

    const personajePorHijo: Record<string, string[]> = {};
    for (const hijo of hijos) {
      const lista = hijo.personajes
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
      if (lista.length > 0) personajePorHijo[hijo.referencia] = lista;
    }

    const elegida =
      PRIORIDADES.find((p) => p.clave === prioridad) ?? PRIORIDADES[1]!;

    // El kit ya no lleva contacto: viaja autenticado por la cookie de sesion
    // (paso 1) y la tuberia resuelve el usuario_id del Bearer que reenvia el
    // Route Handler. El destinatario del aviso es esa cuenta.

    // Las preferencias del paso 3 son del HOGAR: las mismas viajan por las dos
    // rutas. En la verificada las lee el recomendador ya; en la subida quedan
    // guardadas con la tarea para armar el kit cuando un administrador apruebe.
    const preferencias = {
      pesos: elegida.pesos,
      disposicion_sobreprecio: elegida.disposicion_sobreprecio,
      ...(Object.keys(personajePorHijo).length > 0
        ? { personaje_por_hijo: personajePorHijo }
        : {}),
    };

    // El hogar se parte en dos rutas distintas (decisión "wait-screen wins"):
    //   • Los hijos con lista VERIFICADA del colegio disparan `crearTrabajo` y
    //     salen con un kit al vuelo (ruta rápida, sin revisión).
    //   • Los hijos que suben el PDF disparan `subirListas`: cada archivo se
    //     importa como una versión PENDIENTE de su (colegio, grado) y el
    //     acudiente espera a que un administrador la apruebe. No hay kit todavía.
    // Si hay al menos un PDF pendiente, el hogar aterriza en la pantalla de
    // verificación (`/recibimos`) aunque algunos kits ya estén listos.
    const hijosVerificados = hijos.filter((hijo) => hijo.entrada === "lista_oficial");
    const hijosArchivo = hijos.filter((hijo) => hijo.entrada === "archivo" && hijo.archivo);

    // Ruta rapida: un hogar de UN solo hijo verificado cuyo (colegio, grado) ya
    // tiene cache bendita salta la cola y aplica su nivel + personaje al vuelo.
    // Un hogar mixto o con hermanos sigue por la ruta de siempre —la cache es por
    // (colegio, grado), no cubre la consolidacion entre hijos.
    const soloHijo = hijos.length === 1 ? hijos[0] : null;
    const canonicoDelHijo =
      soloHijo && soloHijo.entrada === "lista_oficial"
        ? canonicos.find(
            (c) => c.colegio_id === soloHijo.colegioId && c.grado === soloHijo.grado,
          )
        : undefined;

    if (soloHijo && canonicoDelHijo) {
      const personaje = personajePorHijo[soloHijo.referencia]?.[0];
      try {
        const aplicado = await aplicarCanonico({
          colegio_id: canonicoDelHijo.colegio_id,
          grado: canonicoDelHijo.grado,
          anio_lectivo: canonicoDelHijo.anio_lectivo,
          perfil: perfilDeSeleccion(prioridad, Boolean(personaje)),
          ...(personaje ? { personaje } : {}),
        });
        router.push(`/kits/${aplicado.trabajo_id}`);
        return;
      } catch (causa) {
        if (causa instanceof FalloApi) setError(causa.message);
        else setError("No pudimos armar tu kit. Intenta de nuevo.");
        setEnviando(false);
        return;
      }
    }

    try {
      let trabajoInstantaneo: string | null = null;

      if (hijosVerificados.length > 0) {
        const solicitud: SolicitudTrabajo = {
          hijos: hijosVerificados.map<HijoSolicitud>((hijo) => ({
            referencia: hijo.referencia,
            colegio_id: hijo.colegioId,
            grado: hijo.grado,
          })),
          // Lo que el recomendador de verdad lee: pesos + disposición a pagar
          // de más. El encuadre del paso 3 es "hasta dónde estirar el bolsillo".
          preferencias,
        };
        const creado = await crearTrabajo(solicitud, []);
        trabajoInstantaneo = creado.trabajo_id;
      }

      if (hijosArchivo.length > 0) {
        const resultado = await subirListas(
          hijosArchivo.map((hijo) => ({
            referencia: hijo.referencia,
            // El colegio se designa como llegó: DANE del directorio (+ nombre),
            // o solo el nombre escrito a mano. El backend deriva de ahí el
            // `colegio_id` estable y, al aprobar, crea la identidad del colegio.
            ...(hijo.colegioDane
              ? { colegio_dane: hijo.colegioDane, colegio_nombre: hijo.colegioNombre }
              : { colegio_nombre: hijo.colegioNombre }),
            grado: hijo.grado,
          })),
          hijosArchivo.map((hijo) => ({
            referencia: hijo.referencia,
            archivo: hijo.archivo as File,
          })),
          undefined,
          preferencias,
        );
        // Wait-screen wins: aunque haya un kit listo, el hogar va a la pantalla
        // de verificación, con el kit instantáneo enlazado si existe.
        const parametros = new URLSearchParams({ pendientes: String(resultado.subidas.length) });
        if (trabajoInstantaneo) parametros.set("trabajo", trabajoInstantaneo);
        router.push(`/recibimos?${parametros.toString()}`);
        return;
      }

      // Hogar solo con listas verificadas: la espera de siempre.
      router.push(`/esperando/${trabajoInstantaneo}`);
    } catch (causa) {
      if (causa instanceof FalloApi) {
        setError(causa.message);
        // El 422 del §2.1 trae los grados que detecto en el archivo. Son la
        // parte util del rechazo: sin ellos el acudiente no sabe que paginas
        // recortar.
        const detectados = causa.detalle["grados_detectados"];
        if (Array.isArray(detectados)) setGradosDetectados(detectados.map(String));
      } else {
        setError("No pudimos crear el pedido. Intenta de nuevo.");
      }
      setEnviando(false);
    }
  }

  return (
    <form className={styles.pagina} onSubmit={enviar}>
      <header className={styles.encabezado}>
        <h1>Armemos el kit de tu hogar</h1>
        <p>
          Es un pedido por hogar y no por hijo: así podemos juntar lo que se repite
          entre hermanos y cobrarte una caja en vez de dos sueltos.
        </p>
      </header>

      {/* ----------------------------------------------------------- Cuenta */}
      <section className={styles.bloque} aria-labelledby={`${idBase}-cuenta`}>
        <h2 id={`${idBase}-cuenta`} className={styles.tituloBloque}>
          <span className={styles.paso}>1</span> Tu cuenta
        </h2>
        <p className={styles.explicacion}>
          Creas tu cuenta primero. Así guardamos tus kits y te escribimos cuando
          estén listos — armar el kit toma minutos, no segundos, porque una persona
          revisa cada lista para que la calidad no falle.
        </p>
        {sesionLista ? (
          <p className={styles.explicacion} role="status">
            <Check size={16} aria-hidden /> Cuenta lista. Sigue con las listas de tus hijos.
          </p>
        ) : (
          <>
            <div className={styles.dosColumnas}>
              <label className={styles.campo}>
                <span>Correo</span>
                <input
                  type="email"
                  value={correo}
                  onChange={(e) => setCorreo(e.target.value)}
                  placeholder="tucorreo@ejemplo.com"
                  autoComplete="email"
                  required
                />
              </label>
              {!yaTengoCuenta && (
                <label className={styles.campo}>
                  <span>Tu nombre</span>
                  <input
                    type="text"
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                    placeholder="Cómo te llamas"
                    autoComplete="name"
                    required
                  />
                </label>
              )}
            </div>
            <div className={styles.dosColumnas}>
              {!yaTengoCuenta && (
                <label className={styles.campo}>
                  <span>Celular</span>
                  <input
                    type="tel"
                    value={celular}
                    onChange={(e) => setCelular(e.target.value)}
                    placeholder="+57 300 123 4567"
                    autoComplete="tel"
                    required
                  />
                </label>
              )}
              <label className={styles.campo}>
                <span>Clave</span>
                <input
                  type="password"
                  value={clave}
                  onChange={(e) => setClave(e.target.value)}
                  placeholder="Al menos 8 caracteres"
                  autoComplete={yaTengoCuenta ? "current-password" : "new-password"}
                  minLength={8}
                  required
                />
              </label>
            </div>
            <div className={styles.barraAccion}>
              <button
                type="button"
                className={styles.enviar}
                onClick={() => void resolverCuenta()}
                disabled={!cuentaCompletable || resolviendoCuenta}
              >
                {resolviendoCuenta
                  ? "Un momento…"
                  : yaTengoCuenta
                    ? "Iniciar sesión"
                    : "Crear mi cuenta"}
              </button>
              <button
                type="button"
                className={styles.agregar}
                onClick={() => setYaTengoCuenta((v) => !v)}
              >
                {yaTengoCuenta ? "Quiero crear una cuenta" : "Ya tengo cuenta"}
              </button>
            </div>
          </>
        )}
      </section>

      {/* ------------------------------------------------------------ Hijos */}
      <section className={styles.bloque} aria-labelledby={`${idBase}-hijos`}>
        <h2 id={`${idBase}-hijos`} className={styles.tituloBloque}>
          <span className={styles.paso}>2</span> De quién es la lista
        </h2>

        {hijos.map((hijo, indice) => {
          const colegio = porId.get(hijo.colegioId);
          return (
            <fieldset key={hijo.referencia} className={styles.hijo}>
              <legend className={styles.leyenda}>
                Hijo {indice + 1}
                {hijos.length > 1 && (
                  <button
                    type="button"
                    className={styles.quitar}
                    onClick={() => setHijos((a) => a.filter((_, i) => i !== indice))}
                  >
                    Quitar
                  </button>
                )}
              </legend>

              {/* La ruta se elige PRIMERO: cambia cómo se designa el colegio.
                  "Usar la lista que ya tiene el colegio" busca entre los aliados;
                  "subir archivo" busca en el directorio de Bogotá (o a mano) un
                  colegio que quizá aún no es aliado. Al cambiar de ruta se limpia
                  el colegio y el grado: no se arrastran de una a la otra. */}
              <div className={styles.entradas} role="group" aria-label="Cómo nos das la lista">
                {(
                  [
                    ["lista_oficial", "Usar la lista que ya tiene el colegio"],
                    ["archivo", "Subir el archivo que me mandaron"],
                  ] as [Entrada, string][]
                ).map(([valor, etiqueta]) => (
                  <label
                    key={valor}
                    className={`${styles.opcionEntrada} ${
                      hijo.entrada === valor ? styles.opcionActiva : ""
                    }`}
                  >
                    <input
                      type="radio"
                      name={`entrada-${hijo.referencia}`}
                      value={valor}
                      checked={hijo.entrada === valor}
                      onChange={() =>
                        cambiar(indice, {
                          entrada: valor,
                          grado: "",
                          colegioId: "",
                          colegioDane: "",
                          colegioNombre: "",
                        })
                      }
                    />
                    {etiqueta}
                  </label>
                ))}
              </div>

              {hijo.entrada === "lista_oficial" ? (
                <SelectorColegio
                  colegios={colegios}
                  valor={hijo.colegioId}
                  onElegir={(colegioId) => cambiar(indice, { colegioId, grado: "" })}
                />
              ) : (
                <BuscadorDirectorio
                  dane={hijo.colegioDane}
                  nombre={hijo.colegioNombre}
                  onElegir={({ dane, nombre }) =>
                    cambiar(indice, { colegioDane: dane, colegioNombre: nombre, grado: "" })
                  }
                  onEscribir={(nombre) =>
                    cambiar(indice, { colegioDane: "", colegioNombre: nombre, grado: "" })
                  }
                />
              )}

              {(() => {
                // La ruta "lista oficial" solo puede usar grados VERIFICADOS del
                // aliado (los únicos con la ruta rápida a optimización). La ruta
                // "subir archivo" ofrece todos los grados canónicos una vez que
                // hay un colegio designado: el grado real lo confirma el PDF, y
                // esto es lo que hace usable un colegio sin lista verificada.
                const grados =
                  hijo.entrada === "archivo"
                    ? hijo.colegioNombre
                      ? GRADOS_CANONICOS
                      : []
                    : (colegio?.grados ?? []);
                if (grados.length === 0) return null;
                return (
                  <div className={styles.gradoBloque}>
                    <span className={styles.campoRotulo}>Grado</span>
                    <div
                      className={styles.gradoChips}
                      role="radiogroup"
                      aria-label="Elige el grado"
                    >
                      {grados.map((g) => {
                        const activo = hijo.grado === g;
                        return (
                          <button
                            key={g}
                            type="button"
                            role="radio"
                            aria-checked={activo}
                            className={`${styles.chipGrado} ${activo ? styles.chipGradoActivo : ""}`}
                            onClick={() => cambiar(indice, { grado: g })}
                          >
                            {g}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              {hijo.entrada === "archivo" && (
                <div className={styles.zonaArchivo}>
                  {/* El aviso va ANTES de subir, no como error despues de
                      esperar: una restriccion que solo aparece cuando ya
                      perdiste el tiempo es una restriccion mal puesta. */}
                  <p className={styles.reglaArchivo}>
                    Sube solo las páginas del grado de tu hijo. Si mandas el PDF
                    completo del colegio con los trece grados no lo procesamos, porque
                    un kit armado con los útiles de otro grado es peor que no tener
                    kit.
                  </p>
                  <input
                    id={`archivo-${hijo.referencia}`}
                    type="file"
                    className={styles.inputArchivo}
                    accept={EXTENSIONES_ACEPTADAS.join(",")}
                    onChange={(e) => {
                      elegirArchivo(indice, e.target.files?.[0]);
                      e.target.value = "";
                    }}
                  />
                  <label htmlFor={`archivo-${hijo.referencia}`} className={styles.soltar}>
                    <strong>Haz clic para elegir el archivo</strong>
                    <span>PDF, JPG, PNG o WEBP · hasta 10 MB</span>
                  </label>

                  {hijo.archivo && (
                    <p className={styles.archivoElegido}>
                      {hijo.archivo.name} · {formatearTamano(hijo.archivo.size)}
                    </p>
                  )}
                  {hijo.errorArchivo && (
                    <p className={styles.errorCampo} role="alert">
                      {hijo.errorArchivo}
                    </p>
                  )}

                  {/* No hay que "sugerir" nada aparte: el archivo que subes ES la
                      semilla. Lo revisamos, armamos tu kit y de paso el colegio y
                      el grado quedan verificados para el próximo acudiente del
                      mismo colegio. Un solo paso, no dos. */}
                  {hijo.colegioNombre && hijo.grado && (
                    <p className={styles.sugerenciaOk} role="status">
                      <Check size={16} strokeWidth={3} aria-hidden="true" />
                      Con esto revisamos tu lista, armamos tu kit y dejamos {hijo.colegioNombre} ·{" "}
                      {hijo.grado} verificado para los demás.
                    </p>
                  )}
                </div>
              )}

              <SelectorPersonaje
                etiquetaHijo={`Hijo ${indice + 1}`}
                valor={hijo.personajes}
                onChange={(personajes) => cambiar(indice, { personajes })}
                surtidos={surtidos}
              />
            </fieldset>
          );
        })}

        {hijos.length < 4 && (
          <button
            type="button"
            className={styles.agregar}
            onClick={() => setHijos((a) => [...a, hijoVacio(a.length + 1)])}
          >
            + Agregar otro hijo
          </button>
        )}
      </section>

      {/* ----------------------------------------------------- Preferencias */}
      <section className={styles.bloque} aria-labelledby={`${idBase}-preferencias`}>
        <h2 id={`${idBase}-preferencias`} className={styles.tituloBloque}>
          <span className={styles.paso}>3</span> Cuál de los tres te marcamos
        </h2>
        <p className={styles.explicacion}>
          Los tres kits llevan la misma lista y la misma calidad. Lo único que cambia
          es cuánto gastas. Dinos hasta dónde quieres estirar el bolsillo y te marcamos
          uno; los otros dos quedan a la vista. No preguntamos por el estrato ni por
          nada del hogar.
        </p>

        <fieldset className={styles.opciones}>
          <legend className={styles.leyendaSimple}>Cuánto quieres gastar</legend>
          {PRIORIDADES.map((opcion) => (
            <label
              key={opcion.clave}
              className={`${styles.tarjetaPrioridad} ${
                prioridad === opcion.clave ? styles.opcionActiva : ""
              }`}
            >
              <input
                type="radio"
                name="prioridad"
                value={opcion.clave}
                checked={prioridad === opcion.clave}
                onChange={() => setPrioridad(opcion.clave)}
              />
              <span className={styles.prioridadTexto}>
                <strong>{opcion.titulo}</strong>
                <span className={styles.prioridadDetalle}>{opcion.detalle}</span>
              </span>
            </label>
          ))}
        </fieldset>
      </section>

      {error && (
        <div className={styles.errorCaja} role="alert">
          <strong>{error}</strong>
          {gradosDetectados.length > 0 && (
            <p>Detectamos estos grados en el archivo: {gradosDetectados.join(", ")}.</p>
          )}
        </div>
      )}

      <div className={styles.barraAccion}>
        <button type="submit" className={styles.enviar} disabled={!listo || enviando}>
          {enviando ? "Creando tu pedido…" : "Armar mis tres kits"}
        </button>
        {!listo && (
          <p className={styles.faltante}>
            {sesionLista
              ? "Falta el colegio y el grado de cada hijo."
              : "Primero crea tu cuenta o inicia sesión (paso 1)."}
          </p>
        )}
      </div>
    </form>
  );
}
