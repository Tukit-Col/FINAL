"use client";

import { useCallback, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, Check, School, LogIn, UserPlus, Pencil } from "lucide-react";
import {
  formatearTamano,
  validarArchivo,
  EXTENSIONES_ACEPTADAS,
  GRADOS_CANONICOS,
  type Colegio,
  type GradoCanonico,
  type HijoNuevo,
  type HijoSolicitud,
  type MatriculaAcudiente,
  type PerfilKit,
  type Pesos,
  type SolicitudTrabajo,
} from "@tukit/contrato";
import {
  aplicarCanonico,
  crearTrabajo,
  subirListas,
  registrarAcudiente,
  guardarMatriculas,
  FalloApi,
} from "@/lib/api-navegador";
import SelectorPersonaje from "./SelectorPersonaje";
import styles from "./Empezar.module.css";

interface HijoFormulario {
  referencia: string;
  // El colegio se designa de UNA de tres formas, y la ruta se DERIVA de cuál está
  // puesta (ya no hay un campo `entrada`): un `colegioId` de aliado (ruta "lista
  // oficial"); el DANE del directorio de Bogotá + nombre (colegio del directorio,
  // aún no aliado); o solo el nombre escrito a mano. El backend deriva el
  // `colegio_id` estable de lo que llegue; aquí se guardan las tres piezas y se
  // manda la que corresponda. El buscador reconduce por `colegioId` cuando el
  // DANE elegido en el directorio es el de un aliado, para no duplicarlo.
  colegioId: string;
  colegioDane: string;
  colegioNombre: string;
  grado: string;
  // Apodo OPCIONAL del menor, solo en el camino "soy nuevo usuario". Nunca el
  // nombre legal completo: para armar un kit basta colegio+grado, y por el
  // principio de minimizacion (Ley 1581 de 2012, Art. 4) no recolectamos mas de
  // lo indispensable de un menor. Viaja al backend como `nombre_cifrado`.
  apodo: string;
  // Distingue un hijo NUEVO (que el acudiente teclea ahora) de uno PRECARGADO
  // desde sus matrículas ya guardadas. Con sesión, solo los nuevos se guardan en
  // la cuenta y solo ellos ofrecen campo de apodo editable; el apodo de un hijo
  // precargado se muestra en solo-lectura (no se re-escribe dato del menor).
  precargado: boolean;
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
// Aparte va el tope de gasto (opcional): con tope, se marca la mejor marca que
// cabe en él, sea cual sea la opción elegida.
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
    apodo: "",
    precargado: false,
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

// Une una lista en español natural: "a", "a y b", "a, b y c". Se usa para armar
// el mensaje de qué falta sin comas colgando.
function unirEnLista(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

// -------------------------------------------------------- Buscador de colegio
//
// Un ÚNICO buscador por hijo que mezcla dos fuentes que el padre no distingue:
// los colegios aliados de Tukit y el directorio de Bogotá. La búsqueda del
// directorio es del lado del cliente sobre el JSON ya cargado; no pega a ningún
// servicio (decisión: directorio buscable, no sembrado).

// Una entrada del directorio estático de colegios de Bogotá
// (`/directorio-colegios.json`, ~3k colegios). NO es un colegio aliado: es la
// guía oficial para que el acudiente designe SU colegio aunque Tukit todavía no
// lo tenga.
interface EntradaDirectorio {
  dane: string;
  nombre: string;
  localidad: string;
}

// El directorio se carga UNA vez y se comparte entre todos los hijos: es el
// mismo JSON estático. Se memoiza en un módulo para no re-descargar 300 KB por
// cada `<BuscadorColegio>` que se monte.
let directorioPromesa: Promise<EntradaDirectorio[]> | null = null;
function cargarDirectorio(): Promise<EntradaDirectorio[]> {
  if (!directorioPromesa) {
    directorioPromesa = fetch("/directorio-colegios.json")
      .then((r) => (r.ok ? (r.json() as Promise<EntradaDirectorio[]>) : []))
      .catch(() => []);
  }
  return directorioPromesa;
}

// Plegado de mayúsculas y acentos, mismo idioma que el explorador del catálogo
// (`ExploradorCatalogo.tsx`): así "agustiniano" encuentra "AGUSTINIANO".
function normalizar(texto: string): string {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

// La leyenda que el aliado muestra bajo su nombre, igual en la lista y en la
// tarjeta del elegido: cuántos grados tiene ya con lista verificada.
function metaAliado(c: Colegio): string {
  return c.grados.length === 0
    ? "Sin lista verificada · sube el archivo"
    : `${c.grados.length} ${c.grados.length === 1 ? "grado verificado" : "grados verificados"}`;
}

function BuscadorColegio({
  colegiosAliados,
  colegioId,
  colegioDane,
  colegioNombre,
  onElegirAliado,
  onElegirDirectorio,
  onEscribir,
  onCambiar,
}: {
  colegiosAliados: Colegio[];
  colegioId: string;
  colegioDane: string;
  colegioNombre: string;
  // Eligió una fila que resultó ser un aliado (por su nombre Tukit o por casar el
  // DANE del directorio con el de un aliado): viaja el `colegio_id` real, así el
  // backend NO lo re-deriva ni lo da de alta de nuevo (evita el duplicado).
  onElegirAliado: (colegioId: string) => void;
  // Eligió una entrada del directorio que NO es aliado: viaja el DANE (que deriva
  // el id) y el nombre; nacerá como colegio nuevo cuando se apruebe su lista.
  onElegirDirectorio: (entrada: { dane: string; nombre: string }) => void;
  // No estaba en ninguna fuente y lo escribió a mano: solo el nombre.
  onEscribir: (nombre: string) => void;
  // Deshace la elección para volver a buscar.
  onCambiar: () => void;
}) {
  const [directorio, setDirectorio] = useState<EntradaDirectorio[]>([]);
  const [busqueda, setBusqueda] = useState("");
  // Cargar el directorio al primer foco/tecleo, no al montar: pesa ~300 KB y no
  // hace falta hasta que el padre empieza a escribir.
  const asegurarCargado = useCallback(() => {
    if (directorio.length === 0) cargarDirectorio().then(setDirectorio);
  }, [directorio.length]);

  // Índices normalizados una sola vez (no por tecla): el de aliados incluye un
  // mapa por DANE —primero-gana ante una colisión de DANE, saltando los nulos—
  // que es la clave de reconducir al aliado en vez de duplicarlo.
  const indexAliados = useMemo(() => {
    const porDane = new Map<string, { colegio: Colegio; buscable: string }>();
    const lista = colegiosAliados.map((c) => {
      const entry = { colegio: c, buscable: normalizar(c.nombre) };
      if (c.dane && !porDane.has(c.dane)) porDane.set(c.dane, entry);
      return entry;
    });
    return { lista, porDane };
  }, [colegiosAliados]);
  const directorioNorm = useMemo(
    () => directorio.map((entrada) => ({ entrada, buscable: normalizar(entrada.nombre) })),
    [directorio],
  );
  const directorioDanes = useMemo(
    () => new Set(directorio.map((e) => e.dane)),
    [directorio],
  );

  const qn = normalizar(busqueda.trim());
  const resultados = useMemo(() => {
    if (qn.length < 3) return { aliados: [] as { colegio: Colegio; etiqueta: string }[], directorio: [] as EntradaDirectorio[] };
    const aliados: { colegio: Colegio; etiqueta: string }[] = [];
    const yaAliado = new Set<string>();
    // (a) Entradas del directorio que SON un aliado (comparten DANE). Casan por el
    //     nombre del directorio O por el nombre Tukit del aliado, para que tanto
    //     "agustiniano" como "cacs" den con la misma fila. Etiqueta compuesta.
    for (const { entrada, buscable } of directorioNorm) {
      const aliado = indexAliados.porDane.get(entrada.dane);
      if (!aliado || yaAliado.has(aliado.colegio.colegio_id)) continue;
      if (buscable.includes(qn) || aliado.buscable.includes(qn)) {
        yaAliado.add(aliado.colegio.colegio_id);
        aliados.push({ colegio: aliado.colegio, etiqueta: `${entrada.nombre} · ${aliado.colegio.nombre}` });
      }
    }
    // (b) Aliados que NO están en el directorio (sin DANE, o su DANE no aparece):
    //     los que casan por su nombre Tukit, con etiqueta simple.
    for (const { colegio, buscable } of indexAliados.lista) {
      if (colegio.dane && directorioDanes.has(colegio.dane)) continue;
      if (buscable.includes(qn) && !yaAliado.has(colegio.colegio_id)) {
        yaAliado.add(colegio.colegio_id);
        aliados.push({ colegio, etiqueta: colegio.nombre });
      }
    }
    // (2) Entradas del directorio que NO son aliados, tope 30 como antes.
    const dir = directorioNorm
      .filter(({ entrada, buscable }) => !indexAliados.porDane.has(entrada.dane) && buscable.includes(qn))
      .slice(0, 30)
      .map(({ entrada }) => entrada);
    return { aliados, directorio: dir };
  }, [directorioNorm, directorioDanes, indexAliados, qn]);

  // Ya eligió (aliado, directorio o a mano): se muestra el elegido con opción de
  // cambiarlo, en vez de la lista, para que el paso quede claramente resuelto. El
  // aliado se resuelve desde `colegiosAliados` (ya cargado, sin esperar el JSON).
  if (colegioId || colegioNombre) {
    const aliado = colegioId ? colegiosAliados.find((c) => c.colegio_id === colegioId) : undefined;
    const nombre = aliado?.nombre ?? colegioNombre;
    return (
      <div className={styles.colegioBloque}>
        <span className={styles.campoRotulo}>Busca el colegio de tu hijo</span>
        <div className={`${styles.tarjetaColegio} ${styles.colegioActivo}`}>
          <span className={styles.logoColegio} aria-hidden="true">
            {aliado?.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={aliado.logo_url} alt="" />
            ) : (
              <span className={styles.logoIniciales}>{iniciales(nombre)}</span>
            )}
          </span>
          <span className={styles.colegioTexto}>
            <span className={styles.colegioNombre}>{nombre}</span>
            <span className={styles.colegioMeta}>
              {aliado
                ? metaAliado(aliado)
                : colegioDane
                  ? `Directorio de Bogotá · DANE ${colegioDane}`
                  : "Escrito a mano · lo verificamos nosotros"}
            </span>
          </span>
          <button
            type="button"
            className={styles.cambiarColegio}
            onClick={() => {
              onCambiar();
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
      <span className={styles.campoRotulo}>Busca el colegio de tu hijo</span>
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
          placeholder="Escribe el nombre de tu colegio…"
          aria-label="Buscar el colegio de tu hijo"
        />
      </div>
      {qn.length >= 3 && (
        <div className={styles.listaColegios} role="listbox" aria-label="Colegios">
          {resultados.aliados.map(({ colegio, etiqueta }) => (
            <button
              key={`aliado-${colegio.colegio_id}`}
              type="button"
              role="option"
              aria-selected="false"
              className={styles.tarjetaColegio}
              onClick={() => onElegirAliado(colegio.colegio_id)}
            >
              <span className={styles.logoColegio} aria-hidden="true">
                {colegio.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={colegio.logo_url} alt="" />
                ) : (
                  <span className={styles.logoIniciales}>{iniciales(colegio.nombre)}</span>
                )}
              </span>
              <span className={styles.colegioTexto}>
                <span className={styles.colegioNombre}>{etiqueta}</span>
                <span className={styles.colegioMeta}>{metaAliado(colegio)}</span>
              </span>
            </button>
          ))}
          {resultados.directorio.map((e) => (
            <button
              key={`dir-${e.dane}`}
              type="button"
              role="option"
              aria-selected="false"
              className={styles.tarjetaColegio}
              onClick={() => onElegirDirectorio({ dane: e.dane, nombre: e.nombre })}
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
          {/* No está en ninguna fuente: se escribe a mano. El backend deriva el id
              del nombre normalizado, así que dos acudientes que escriban el mismo
              colegio convergen a la misma versión. */}
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
      {qn.length > 0 && qn.length < 3 && (
        <p className={styles.sinColegios}>
          <School size={18} strokeWidth={2} aria-hidden="true" />
          Escribe al menos tres letras del nombre.
        </p>
      )}
    </div>
  );
}

// Los cuatro estados de la pantalla. Es la particion pedida: quien ya tiene
// cuenta no re-teclea a sus hijos; quien es nuevo se registra en el mismo flujo.
//   elegir      -> sin sesion y sin escoger: solo el encabezado y los dos botones
//   existente   -> "ya tengo cuenta": texto + CTA a /ingresar (vuelve a /empezar)
//   nuevo       -> "soy nuevo usuario": seccion Registrate + hijos + prioridad
//   autenticado -> ya hay sesion: hijos precargados + a-donde-avisamos + prioridad
type Modo = "elegir" | "existente" | "nuevo" | "autenticado";

export default function FormularioEmpezar({
  colegios,
  surtidos,
  canonicos,
  sesion = null,
  matriculasIniciales = [],
}: {
  colegios: Colegio[];
  surtidos: string[];
  canonicos: GradoCanonico[];
  // La sesion trae solo el correo (para precargar el contacto); si es null, el
  // acudiente aun no entro y hay que ofrecerle los dos caminos.
  sesion?: { correo: string } | null;
  // Colegio+grado de cada hijo del portador, sin dato del menor. Precarga el
  // camino "ya tengo cuenta"; vacio si no hay sesion o el backend no responde.
  matriculasIniciales?: MatriculaAcudiente[];
}) {
  const router = useRouter();
  const idBase = useId();

  // Sin sesion arranca en "nuevo" (soy nuevo usuario) ya marcado y con el
  // formulario de registro a la vista; el acudiente puede cambiar a "ya tengo
  // cuenta". Con sesion viva, "autenticado".
  const [modo, setModo] = useState<Modo>(sesion ? "autenticado" : "nuevo");
  // Con sesion y matriculas, un bloque por hijo ya con su colegio y grado (ruta
  // "lista oficial", que es la que valida el envio). Sin eso, un hijo en blanco.
  // Un colegio es "aliado" en cuanto tiene su primer grado verificado. Mismo
  // criterio que el tipo Colegio y el admin (apps/admin/.../colegios/page.tsx).
  const colegiosAliados = useMemo(
    () => colegios.filter((c) => c.es_partner ?? c.grados.length > 0),
    [colegios],
  );
  const [hijos, setHijos] = useState<HijoFormulario[]>(() => {
    // Solo se precarga colegio+grado si la matrícula es de un aliado; si no, el
    // hijo arranca vacío (como uno nuevo) para no dejar seleccionado un colegio
    // que el selector, ya filtrado a aliados, no muestra.
    const idsAliados = new Set(colegiosAliados.map((c) => c.colegio_id));
    return matriculasIniciales.length > 0
      ? matriculasIniciales.map((m, i) => {
          const esAliado = idsAliados.has(m.colegio_id);
          return {
            ...hijoVacio(i + 1),
            colegioId: esAliado ? m.colegio_id : "",
            grado: esAliado ? m.grado : "",
            // El apodo del propio hijo baja descifrado en la precarga; solo se
            // conserva si el colegio es aliado (si no, el hijo arranca vacío).
            apodo: esAliado ? (m.apodo ?? "") : "",
            // Marcado como precargado solo si de verdad quedó con su matrícula
            // (colegio aliado): así no se re-guarda ni pide apodo de nuevo.
            precargado: esAliado,
          };
        })
      : [hijoVacio(1)];
  });
  const [correo, setCorreo] = useState(sesion?.correo ?? "");
  const [clave, setClave] = useState("");
  const [celular, setCelular] = useState("");
  const [prioridad, setPrioridad] = useState<ClavePrioridad>("equilibrio");
  // Solo dígitos: el tope viaja como entero en pesos (`presupuesto_por_hijo`).
  const [presupuesto, setPresupuesto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Aviso NO bloqueante (ámbar): p.ej. no pudimos guardar los hijos nuevos en la
  // cuenta, pero el kit se arma igual. Distinto de `error`, que sí detiene.
  const [aviso, setAviso] = useState<string | null>(null);
  const [gradosDetectados, setGradosDetectados] = useState<string[]>([]);
  // Lo que ya salió bien en un envío que aún no terminó, para no repetirlo al
  // reintentar. La "firma" es el payload serializado del paso: si el acudiente
  // cambia esos datos deja de coincidir y el paso se rehace; si no, se reutiliza
  // y no se duplica. Se limpia solo: al navegar con éxito, /empezar se desmonta.
  const [progreso, setProgreso] = useState<{
    registroFirma?: string;
    matriculasFirma?: string;
    trabajoId?: string;
    trabajoFirma?: string;
  }>({});

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

  // Un grado tiene lista VERIFICADA si el colegio la trae en `colegio.grados`
  // (ver catalogo.ts): son los únicos grados con lista revisada y ruta rápida a
  // optimización.
  function gradoVerificado(hijo: HijoFormulario): boolean {
    return porId.get(hijo.colegioId)?.grados.includes(hijo.grado) ?? false;
  }

  // Cuándo el hijo se resuelve adjuntando un archivo en vez de con la lista
  // verificada del colegio: SIEMPRE que no sea un aliado (no hay `colegioId`), y
  // también en un aliado cuando el grado elegido no tiene lista verificada (ahí el
  // acudiente adjunta la lista de ESE grado). En ambos casos el archivo viaja en
  // el mismo `crearTrabajo`/`subirListas` de hoy; no hay endpoint nuevo.
  function necesitaArchivo(hijo: HijoFormulario): boolean {
    if (!hijo.colegioId) return true;
    return hijo.grado !== "" && !gradoVerificado(hijo);
  }

  // Un hijo está completo según su ruta (derivada de `colegioId`). El grado es
  // obligatorio siempre. Sin `colegioId` (colegio del directorio o a mano) basta
  // el nombre y el archivo. Con `colegioId` de aliado, si el grado no tiene lista
  // verificada hace falta también el archivo adjunto (zonaListaGrado).
  function hijoCompleto(hijo: HijoFormulario): boolean {
    if (!hijo.grado) return false;
    if (!hijo.colegioId) return Boolean(hijo.colegioNombre) && hijo.archivo !== null;
    if (necesitaArchivo(hijo)) return hijo.archivo !== null;
    return true; // aliado con grado verificado: la lista ya existe
  }

  // El camino "soy nuevo usuario" crea la cuenta, asi que ahi la clave es
  // obligatoria; en los demas caminos no hay clave que pedir.
  const listo =
    correo.trim().length > 3 &&
    celular.trim().length > 6 &&
    (modo !== "nuevo" || clave.length >= 6) &&
    hijos.every(hijoCompleto);

  // Qué falta EXACTAMENTE para poder enviar, traduciendo a texto los mismos
  // predicados que ya calculan `listo` y `necesitaArchivo` (no hay validación
  // nueva). Por hijo se reporta solo el primer paso ACCIONABLE —colegio, luego
  // grado, luego lista— porque los chips de grado y la zona de subida no se
  // pintan hasta que hay colegio: pedir "el grado" sin colegio señalaría un campo
  // que aún no está en pantalla.
  const faltantesContacto: string[] = [];
  if (correo.trim().length <= 3) faltantesContacto.push("tu correo");
  if (modo === "nuevo" && clave.length < 6) faltantesContacto.push("una contraseña");
  if (celular.trim().length <= 6) faltantesContacto.push("tu celular");

  const faltantesHijos: string[] = [];
  hijos.forEach((hijo, i) => {
    const suf = hijos.length > 1 ? ` del hijo ${i + 1}` : "";
    const tieneColegio = Boolean(hijo.colegioId) || Boolean(hijo.colegioNombre);
    if (!tieneColegio) faltantesHijos.push(`el colegio${suf}`);
    else if (!hijo.grado) faltantesHijos.push(`el grado${suf}`);
    else if (necesitaArchivo(hijo) && hijo.archivo === null) faltantesHijos.push(`la lista${suf}`);
  });

  // En "soy nuevo usuario" el registro va primero en pantalla; en el resto, los hijos.
  const faltantes =
    modo === "nuevo"
      ? [...faltantesContacto, ...faltantesHijos]
      : [...faltantesHijos, ...faltantesContacto];

  // Renumeracion de las secciones sin duplicar JSX: en "nuevo" hay tres pasos
  // (1 Registrate, 2 hijos, 3 prioridad) y NO se pinta "a donde te avisamos"
  // (el correo y el celular ya se capturan en Registrate). En el resto sigue
  // igual que siempre: 1 hijos, 2 contacto, 3 prioridad.
  const mostrarFormulario = modo === "nuevo" || modo === "autenticado";
  const pasoHijos = modo === "nuevo" ? 2 : 1;
  const pasoContacto = 2;
  const pasoPrioridad = 3;

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!listo || enviando) return;
    setEnviando(true);
    setError(null);
    setAviso(null);
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

    const contacto = { correo: correo.trim(), celular: celular.trim() };

    // Las preferencias del paso 3 son del HOGAR: las mismas viajan por las dos
    // rutas. En la verificada las lee el recomendador ya; en la subida quedan
    // guardadas con la tarea para armar el kit cuando un administrador apruebe.
    // El tope es opcional. Con tope, el recomendador marca la mejor marca que
    // cabe en él (el Premium ajustado al presupuesto si el de siempre no cabe).
    const presupuestoPesos = Number.parseInt(presupuesto, 10);
    const conPresupuesto = Number.isSafeInteger(presupuestoPesos) && presupuestoPesos > 0;
    const preferencias = {
      pesos: elegida.pesos,
      disposicion_sobreprecio: elegida.disposicion_sobreprecio,
      ...(conPresupuesto ? { presupuesto_por_hijo: presupuestoPesos } : {}),
      ...(Object.keys(personajePorHijo).length > 0
        ? { personaje_por_hijo: personajePorHijo }
        : {}),
    };

    // Camino "soy nuevo usuario": ANTES de armar nada se da de alta la cuenta y
    // los hijos (idempotente en el backend); el registro es un paso ADICIONAL, no
    // un reemplazo del armado del kit. Solo viajan los hijos con colegio ALIADO
    // (`colegioId` real): `HijoRegistro.colegio_id` es un UUID requerido, y los de
    // la ruta "No encontré mi colegio" todavía no lo tienen —esos se dan de alta
    // cuando un administrador aprueba la lista que subieron—. Si el alta falla no
    // seguimos: su propio catch lo reporta y no se crea ningún trabajo.
    if (modo === "nuevo") {
      const registro = {
        correo: contacto.correo,
        clave,
        celular: contacto.celular,
        hijos: hijos
          .filter((hijo) => hijo.colegioId)
          .map((hijo) => ({
            colegio_id: hijo.colegioId,
            grado: hijo.grado,
            // Apodo solo si lo dieron: es opcional y minimizamos el dato del menor.
            ...(hijo.apodo.trim() ? { apodo: hijo.apodo.trim() } : {}),
          })),
      };
      // El alta es idempotente en el backend, pero no la repetimos en cada
      // reintento: guardamos la firma de lo ya registrado y solo volvemos a llamar
      // si el acudiente cambió esos datos. Así el registro sobrevive al reintento.
      const firmaRegistro = JSON.stringify(registro);
      if (progreso.registroFirma !== firmaRegistro) {
        try {
          await registrarAcudiente(registro);
          setProgreso((p) => ({ ...p, registroFirma: firmaRegistro }));
        } catch (causa) {
          if (causa instanceof FalloApi) setError(causa.message);
          else setError("No pudimos crear tu cuenta. Intenta de nuevo.");
          setEnviando(false);
          return;
        }
      }
    }

    // Camino "ya tengo cuenta": guardamos en la cuenta los hijos NUEVOS (los que
    // el acudiente agregó ahora), para que la próxima vez se precarguen. Es un
    // EXTRA sobre el armado del kit: solo van los nuevos de colegio ALIADO (los
    // precargados ya están; los sin `colegioId` todavía no tienen matrícula), y
    // si el guardado falla NO bloqueamos —se avisa y se sigue armando el kit—.
    // Idempotente y con firma, igual que el registro: no se repite en reintentos.
    if (modo === "autenticado") {
      const nuevos: HijoNuevo[] = hijos
        .filter((hijo) => !hijo.precargado && hijo.colegioId)
        .map((hijo) => ({
          colegio_id: hijo.colegioId,
          grado: hijo.grado,
          ...(hijo.apodo.trim() ? { apodo: hijo.apodo.trim() } : {}),
        }));
      if (nuevos.length > 0) {
        const firmaMatriculas = JSON.stringify(nuevos);
        if (progreso.matriculasFirma !== firmaMatriculas) {
          try {
            await guardarMatriculas(nuevos);
            setProgreso((p) => ({ ...p, matriculasFirma: firmaMatriculas }));
          } catch {
            // No bloquea: el kit se arma igual. Solo avisamos que no quedaron
            // guardados en la cuenta (se podrán agregar luego sin perder el kit).
            setAviso(
              "No pudimos guardar tus hijos nuevos en tu cuenta, pero seguimos con tu kit. Podrás agregarlos más tarde.",
            );
          }
        }
      }
    }

    // El hogar se parte en dos rutas (decisión "wait-screen wins"):
    //   • Grado con lista VERIFICADA → `crearTrabajo` (JSON, sin archivo): kit al
    //     vuelo, sin revisión.
    //   • Sube PDF (grado sin verificar de un colegio aliado, o "No encontré mi
    //     colegio") → `subirListas`: el archivo entra como versión PENDIENTE de su
    //     (colegio, grado) y el acudiente espera la aprobación de un administrador.
    // El PDF NUNCA viaja por `crearTrabajo` (`POST /v1/trabajos` es solo JSON, y un
    // multipart daría 400 "no tiene la forma que el contrato espera"): siempre por
    // `subirListas` (`POST /v1/listas/subir`, que acepta multipart). Si hay al menos
    // un PDF pendiente, el hogar aterriza en `/recibimos` aunque algún kit ya esté listo.
    // aliado con grado VERIFICADO: su lista ya existe → crearTrabajo (JSON).
    const hijosVerificados = hijos.filter(
      (hijo) => hijo.colegioId && gradoVerificado(hijo),
    );
    // Suben PDF por `subirListas`: colegio no aliado (sin `colegioId`) y aliado
    // cuyo grado aún no tiene lista verificada. `necesitaArchivo` reúne
    // los dos casos sin duplicar su lógica; el `&& archivo` descarta lo que el gate
    // `listo` ya impide llegar sin adjunto.
    const hijosSubida = hijos.filter((hijo) => necesitaArchivo(hijo) && hijo.archivo);

    // Ruta rapida: un hogar de UN solo hijo verificado cuyo (colegio, grado) ya
    // tiene cache bendita salta la cola y aplica su nivel + personaje al vuelo.
    // Un hogar mixto o con hermanos sigue por la ruta de siempre —la cache es por
    // (colegio, grado), no cubre la consolidacion entre hijos.
    const soloHijo = hijos.length === 1 ? hijos[0] : null;
    const canonicoDelHijo =
      // Solo un grado VERIFICADO puede tomar la ruta rápida. La cache canónica
      // (kit_canonico, inteligencia) y los grados verificados (revisada_en, catálogo)
      // se pueblan por triggers independientes en servicios distintos, sin FK ni join:
      // un (colegio, grado) puede tener entrada canónica sin estar verificado. Sin esta
      // guarda, un grado gris con PDF aplicaría el kit canónico y se perdería el archivo.
      soloHijo && soloHijo.colegioId && gradoVerificado(soloHijo)
        ? canonicos.find(
            (c) => c.colegio_id === soloHijo.colegioId && c.grado === soloHijo.grado,
          )
        : undefined;

    // Con tope de gasto no hay ruta rápida: la cache aplica uno de los tres
    // kits fijos, y el kit que cabe en el tope solo sale del optimizador.
    if (soloHijo && canonicoDelHijo && !conPresupuesto) {
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
        // Si hubo alta ("soy nuevo usuario"), la cookie de sesión ya está puesta:
        // refrescamos para que la Cabecera (Server Component) la lea en el destino.
        if (modo === "nuevo") router.refresh();
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
          contacto,
          hijos: hijosVerificados.map<HijoSolicitud>((hijo) => ({
            referencia: hijo.referencia,
            colegio_id: hijo.colegioId,
            grado: hijo.grado,
          })),
          // Lo que el recomendador de verdad lee: pesos + disposición a pagar
          // de más. El encuadre del paso 3 es "hasta dónde estirar el bolsillo".
          preferencias,
        };
        // Reintento sin huérfanos: si este mismo trabajo ya se creó (misma firma) y
        // luego falló la subida, se reutiliza su id en vez de crear otro. Si el hogar
        // verificado o las preferencias cambiaron, la firma no coincide y se crea el
        // trabajo que toca.
        const firmaTrabajo = JSON.stringify(solicitud);
        if (progreso.trabajoId && progreso.trabajoFirma === firmaTrabajo) {
          trabajoInstantaneo = progreso.trabajoId;
        } else {
          // Sin archivos: la lista verificada ya existe, así que el trabajo viaja en
          // JSON puro. Un PDF aquí forzaría multipart contra `POST /v1/trabajos` (solo
          // JSON) → 400. Los grados sin verificar suben su PDF por `subirListas`.
          const creado = await crearTrabajo(solicitud);
          trabajoInstantaneo = creado.trabajo_id;
          setProgreso((p) => ({ ...p, trabajoId: creado.trabajo_id, trabajoFirma: firmaTrabajo }));
        }
      }

      if (hijosSubida.length > 0) {
        // subirListas no se cachea: es el paso terminal (al éxito navega y retorna),
        // así que nunca hay un reintento después de una subida exitosa; y el backend
        // deduplica por (colegio, grado), así que repetirla es inocua.
        const resultado = await subirListas(
          hijosSubida.map((hijo) => ({
            referencia: hijo.referencia,
            // El colegio se designa según lo que quedó puesto: un aliado (grado sin
            // verificar) viaja por `colegio_id` —incluido el aliado al que el
            // buscador reconduce desde el directorio, que es lo que EVITA el
            // duplicado—; si no, por DANE del directorio (+ nombre) o solo el nombre
            // escrito a mano. El backend deriva de ahí el `colegio_id` estable y, al
            // aprobar, crea la identidad del colegio si aún no existe.
            ...(hijo.colegioId
              ? { colegio_id: hijo.colegioId }
              : hijo.colegioDane
                ? { colegio_dane: hijo.colegioDane, colegio_nombre: hijo.colegioNombre }
                : { colegio_nombre: hijo.colegioNombre }),
            grado: hijo.grado,
          })),
          hijosSubida.map((hijo) => ({
            referencia: hijo.referencia,
            archivo: hijo.archivo as File,
          })),
          contacto,
          preferencias,
        );
        // Wait-screen wins: aunque haya un kit listo, el hogar va a la pantalla
        // de verificación, con el kit instantáneo enlazado si existe.
        const parametros = new URLSearchParams({ pendientes: String(resultado.subidas.length) });
        if (trabajoInstantaneo) parametros.set("trabajo", trabajoInstantaneo);
        router.push(`/recibimos?${parametros.toString()}`);
        if (modo === "nuevo") router.refresh();
        return;
      }

      // Hogar solo con listas verificadas: la espera de siempre.
      router.push(`/esperando/${trabajoInstantaneo}`);
      if (modo === "nuevo") router.refresh();
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

      {/* ------------------------------------------------ Los dos caminos */}
      {/* La particion pedida: justo debajo del encabezado, quien ya tiene
          cuenta la usa (y le precargamos los hijos) y quien es nuevo se
          registra en el mismo flujo. Con sesion viva no se pintan: ya estas
          "autenticado". Reutilizan el patron tarjeta-radio de las entradas. */}
      {modo !== "autenticado" && (
        <div className={styles.dosColumnas} role="group" aria-label="¿Ya tienes cuenta?">
          <button
            type="button"
            className={`${styles.opcionEntrada} ${modo === "existente" ? styles.opcionActiva : ""}`}
            onClick={() => setModo("existente")}
          >
            <LogIn size={16} strokeWidth={2.4} aria-hidden="true" />
            Ya tengo cuenta
          </button>
          <button
            type="button"
            className={`${styles.opcionEntrada} ${modo === "nuevo" ? styles.opcionActiva : ""}`}
            onClick={() => setModo("nuevo")}
          >
            <UserPlus size={16} strokeWidth={2.4} aria-hidden="true" />
            Soy nuevo usuario
          </button>
        </div>
      )}

      {/* Camino "ya tengo cuenta": entrar y volver aqui con los hijos cargados.
          El `destino=/empezar` hace que el login regrese a esta pantalla (no al
          dashboard); el Route Handler solo acepta rutas internas. */}
      {modo === "existente" && (
        <section className={styles.bloque}>
          <p className={styles.explicacion}>
            Entra con tu cuenta y te precargamos a tus hijos: no vuelves a teclear su
            colegio ni su grado, solo eliges el kit.
          </p>
          <Link href="/ingresar?destino=/empezar" className={styles.enviar}>
            <LogIn size={17} strokeWidth={2.6} aria-hidden="true" />
            Ingresar a mi cuenta
          </Link>
        </section>
      )}

      {/* ------------------------------------------------------- Regístrate */}
      {/* Solo en el camino "soy nuevo usuario", ANTES de todo: aqui se capturan
          correo, clave y celular, por eso en este camino se quita "a dónde te
          avisamos". Reutiliza los estilos de esa sección, sin CSS nuevo. */}
      {modo === "nuevo" && (
        <section className={styles.bloque} aria-labelledby={`${idBase}-registro`}>
          <h2 id={`${idBase}-registro`} className={styles.tituloBloque}>
            <span className={styles.paso}>1</span> Regístrate
          </h2>
          <p className={styles.explicacion}>
            Creamos tu cuenta para guardar tus pedidos y avisarte cuando el kit esté
            listo. La próxima vez entras y ya tienes a tus hijos cargados.
          </p>
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
            <label className={styles.campo}>
              <span>Contraseña</span>
              <input
                type="password"
                value={clave}
                onChange={(e) => setClave(e.target.value)}
                placeholder="Elige una contraseña"
                autoComplete="new-password"
                required
              />
            </label>
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
          </div>
        </section>
      )}

      {mostrarFormulario && (
        <>
      {/* ------------------------------------------------------------ Hijos */}
      <section className={styles.bloque} aria-labelledby={`${idBase}-hijos`}>
        <h2 id={`${idBase}-hijos`} className={styles.tituloBloque}>
          <span className={styles.paso}>{pasoHijos}</span> De quién es la lista
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

              {/* Un solo buscador: mezcla aliados y directorio sin que el padre
                  distinga. Al elegir un aliado (por su nombre o porque el DANE del
                  directorio casa con uno) viaja `colegioId` y se reconduce ahí
                  mismo, sin volver a darlo de alta. Al cambiar se limpian las tres
                  piezas y el grado: no se arrastran de una elección a otra. */}
              <BuscadorColegio
                colegiosAliados={colegiosAliados}
                colegioId={hijo.colegioId}
                colegioDane={hijo.colegioDane}
                colegioNombre={hijo.colegioNombre}
                onElegirAliado={(colegioId) =>
                  cambiar(indice, { colegioId, colegioDane: "", colegioNombre: "", grado: "" })
                }
                onElegirDirectorio={({ dane, nombre }) =>
                  cambiar(indice, { colegioId: "", colegioDane: dane, colegioNombre: nombre, grado: "" })
                }
                onEscribir={(nombre) =>
                  cambiar(indice, { colegioId: "", colegioDane: "", colegioNombre: nombre, grado: "" })
                }
                onCambiar={() =>
                  cambiar(indice, { colegioId: "", colegioDane: "", colegioNombre: "", grado: "" })
                }
              />

              {/* Apodo OPCIONAL del menor, SOLO cuando el hijo quedó en un aliado
                  (`colegioId`): un hijo de colegio no aliado se matricula recién al
                  aprobarse su lista, así que aquí el apodo no se guardaría. Nunca el
                  nombre legal: para el kit basta colegio+grado, y minimizamos el
                  dato del menor (Ley 1581 de 2012, Art. 4). Editable para un hijo
                  NUEVO; para uno YA precargado se muestra en solo-lectura —no
                  re-escribimos el dato del menor, solo lo recordamos—. */}
              {hijo.colegioId &&
                (modo === "nuevo" || (modo === "autenticado" && !hijo.precargado)) && (
                  <label className={styles.campo}>
                    <span>Apodo de tu hijo (opcional)</span>
                    <input
                      type="text"
                      value={hijo.apodo}
                      onChange={(e) => cambiar(indice, { apodo: e.target.value })}
                      placeholder="Escribe el apodo de tu hijo para personalizar tu kit"
                      autoComplete="off"
                    />
                  </label>
                )}
              {modo === "autenticado" && hijo.precargado && hijo.apodo && (
                <p className={styles.apodoPrecargado}>Apodo: {hijo.apodo}</p>
              )}

              {/* Selector de grado, DEBAJO del buscador de colegio. Se ofrecen los
                  13 grados canónicos siempre (el grado es obligatorio también sin
                  aliado: el backend lo exige en `HijoSolicitud.grado`). Aparece
                  cuando ya hay colegio designado: un aliado (`colegio`) o un nombre
                  del directorio/escrito a mano. Solo con un aliado los grados con
                  lista verificada (`colegio.grados`) van en azul suave; sin aliado
                  van todos neutros y el grado real lo confirma el PDF. */}
              {(colegio || hijo.colegioNombre) && (
                <div className={styles.gradoBloque}>
                  <span className={styles.campoRotulo}>Grado</span>
                  <div className={styles.gradoChips} role="radiogroup" aria-label="Elige el grado">
                    {GRADOS_CANONICOS.map((g) => {
                      const activo = hijo.grado === g;
                      // La señal de "verificado" (azul) solo aplica a un aliado.
                      const oficial = Boolean(hijo.colegioId);
                      // Un grado está "verificado" si el colegio aliado tiene lista
                      // revisada para él (`colegio.grados`, ver catalogo.ts).
                      const verificado = oficial && (colegio?.grados.includes(g) ?? false);
                      const clase = activo
                        ? styles.chipGradoActivo
                        : verificado
                          ? styles.chipGradoVerificado
                          : "";
                      return (
                        <button
                          key={g}
                          type="button"
                          role="radio"
                          aria-checked={activo}
                          // El color no es la única señal: el lector de pantalla y
                          // el tooltip dicen si el grado tiene lista verificada.
                          aria-label={
                            oficial
                              ? `${g}, ${verificado ? "con lista verificada" : "sin lista verificada"}`
                              : g
                          }
                          title={
                            oficial
                              ? verificado
                                ? "Tiene lista verificada del colegio"
                                : "Sin lista verificada todavía"
                              : undefined
                          }
                          className={`${styles.chipGrado} ${clase}`}
                          onClick={() => cambiar(indice, { grado: g })}
                        >
                          {g}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Grado elegido en un ALIADO que el colegio aún no tiene verificado.
                  En vez de bloquear, se invita a ADJUNTAR la lista de ese grado: el
                  archivo viaja por `subirListas` (reusa `elegirArchivo`/`hijo.archivo`),
                  sin endpoint nuevo. Contenedor propio (`zonaListaGrado`, azul suave)
                  para que se distinga de la zona blanca del colegio no aliado. */}
              {colegio &&
                hijo.grado !== "" &&
                !colegio.grados.includes(hijo.grado) && (
                  <div className={styles.zonaListaGrado}>
                    <span className={styles.campoRotulo}>Subir lista de grado ({hijo.grado})</span>
                    <p className={styles.reglaArchivo}>
                      Este grado todavía no tiene lista verificada del colegio.
                      Adjunta tu lista y la revisamos para armar el kit.
                    </p>
                    <input
                      id={`lista-grado-${hijo.referencia}`}
                      type="file"
                      className={styles.inputArchivo}
                      accept={EXTENSIONES_ACEPTADAS.join(",")}
                      onChange={(e) => {
                        elegirArchivo(indice, e.target.files?.[0]);
                        e.target.value = "";
                      }}
                    />
                    <label htmlFor={`lista-grado-${hijo.referencia}`} className={styles.soltar}>
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
                  </div>
                )}

              {/* Colegio no aliado (sin `colegioId`) ya designado por nombre. Se
                  exige el nombre —no basta `!colegioId`— porque la ruta se deriva:
                  un hijo recién creado también tiene `colegioId` vacío y no debe
                  mostrar la zona de subida antes de elegir colegio. */}
              {!hijo.colegioId && hijo.colegioNombre && (
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

      {/* --------------------------------------------------------- Contacto */}
      {/* En "soy nuevo usuario" NO se pinta: el correo y el celular ya se
          piden en Regístrate. En "autenticado" sí, porque la sesión trae el
          correo pero no el celular, que hay que capturar aquí. */}
      {modo !== "nuevo" && (
      <section className={styles.bloque} aria-labelledby={`${idBase}-contacto`}>
        <h2 id={`${idBase}-contacto`} className={styles.tituloBloque}>
          <span className={styles.paso}>{pasoContacto}</span> A dónde te avisamos
        </h2>
        <p className={styles.explicacion}>
          Armar el kit toma minutos, no segundos, porque una persona revisa cada
          lista para que la calidad no falle. No tienes que quedarte mirando la
          pantalla: te escribimos cuando esté listo.
        </p>
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
        </div>
      </section>
      )}

      {/* ----------------------------------------------------- Preferencias */}
      <section className={styles.bloque} aria-labelledby={`${idBase}-preferencias`}>
        <h2 id={`${idBase}-preferencias`} className={styles.tituloBloque}>
          <span className={styles.paso}>{pasoPrioridad}</span> Cuál de los tres te marcamos
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

        <label className={styles.campo}>
          <span>
            Tope de gasto para el kit <em>(opcional)</em>
          </span>
          <input
            type="text"
            inputMode="numeric"
            value={presupuesto ? `$ ${Number(presupuesto).toLocaleString("es-CO")}` : ""}
            onChange={(e) => setPresupuesto(e.target.value.replace(/\D/g, "").slice(0, 9))}
            placeholder="$ 350.000"
            aria-describedby={`${idBase}-ayuda-presupuesto`}
          />
          <em id={`${idBase}-ayuda-presupuesto`}>
            Si nos dices cuánto quieres gastar como máximo, te marcamos el kit con la mejor
            marca que cabe en ese tope.
          </em>
        </label>
      </section>

      {error && (
        <div className={styles.errorCaja} role="alert">
          <strong>{error}</strong>
          {gradosDetectados.length > 0 && (
            <p>Detectamos estos grados en el archivo: {gradosDetectados.join(", ")}.</p>
          )}
        </div>
      )}

      {/* Aviso no bloqueante: el kit sigue su curso. `role="status"` (no
          "alert") porque no exige acción del acudiente. */}
      {aviso && (
        <div className={styles.avisoCaja} role="status">
          {aviso}
        </div>
      )}

      <div className={styles.barraAccion}>
        <button type="submit" className={styles.enviar} disabled={!listo || enviando}>
          {enviando ? "Creando tu pedido…" : "Armar mis tres kits"}
        </button>
        {!listo && (
          <p className={styles.faltante}>
            {faltantes.length > 0
              ? `${faltantes.length === 1 ? "Falta" : "Faltan"} ${unirEnLista(faltantes)} para continuar.`
              : "Completa los datos que faltan para continuar."}
          </p>
        )}
      </div>
        </>
      )}
    </form>
  );
}
