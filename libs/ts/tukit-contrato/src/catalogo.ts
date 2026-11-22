// Superficie de LECTURA del catalogo. ASUMIDA, no transcrita.
//
// A la hora de escribir esto, `CONTRATO_API.md` estaba en 1.0 y
// no traia la seccion de catalogo: el equipo de backend la iba a agregar como
// 1.1. Todo este fichero es una inferencia a partir de dos fuentes que si
// existen y que el backend tampoco puede contradecir sin migrar la base:
//
//   - `servicios/catalogo/tukit_catalogo/modelos/` (concepto, producto
//     canonico, oferta de tienda, precio con vigencia, lista oficial),
//   - `servicios/catalogo/tukit_catalogo/vista.py`, que ya resuelve esta
//     misma pregunta contra la base y en cuya consulta se ve que campos
//     acompanan a un producto cuando se lo muestra a una persona.
//
// Vive en su propio fichero, y no mezclado con `contrato.ts`, justamente para
// que la diferencia entre "lo que el contrato dice" y "lo que supusimos" se
// pueda ver de un vistazo cuando salga la 1.1.

import type { Dinero, ModoAdquisicion, Nivel, TipoItem, UnidadBase } from "./contrato";

export const VERSION_CATALOGO_ASUMIDA = "1.1-asumida";

export interface TiendaCatalogo {
  slug: string;
  nombre: string;
  tipo: "minorista" | "mayorista" | "editorial" | "propia";
  url_base: string | null;
}

// `precio` y `disponible` admiten nulo con significados DISTINTOS y ninguno de
// los dos es cero ni falso: `precio: null` es "no se conoce el precio" (§1.4) y
// `disponible: null` es "no se observo el stock", que es el caso normal del
// canal mayorista segun `oferta.py`.
export interface OfertaCatalogo {
  tienda: string;
  tienda_nombre: string;
  precio: Dinero | null;
  url: string | null;
  disponible: boolean | null;
  visto_en: string | null;
  confianza_vinculacion: number;
}

export interface ProductoCatalogo {
  sku: string;
  ean: string | null;
  nombre: string;
  descripcion: string | null;
  marca: string | null;
  // `nivel` y `personaje` son ejes ORTOGONALES: un cuaderno de Spiderman
  // tambien tiene nivel de calidad. La restriccion de la base lo impone y la
  // pantalla lo tiene que reflejar, no fundirlos en una sola etiqueta.
  nivel: Nivel;
  personaje: string | null;
  imagen_url: string | null;
  atributos: Record<string, unknown>;
  quality_score: number;
  es_propio: boolean;
  ofertas: OfertaCatalogo[];
}

// El detalle de un producto tal como lo sirve `_producto_publico` del backend:
// es un `ProductoCatalogo` MAS los campos que solo aparecen cuando se pide un
// producto puntual (o la busqueda paginada), no cuando cuelga de un concepto en
// el catalogo de una pieza. La SPA de admin (P4c) los necesita para el
// formulario de edicion: unidad y empaque para el precio por unidad, el concepto
// para poder reclasificar, y `precio_desde`/`tiendas` para el encabezado.
//
// PATCH y reclasificar responden con esta forma (el producto ya actualizado).
export interface ProductoCatalogoDetalle extends ProductoCatalogo {
  unidad_base: UnidadBase;
  unidades_por_empaque: number;
  concepto: { codigo: string; nombre: string };
  precio_desde: Dinero | null;
  tiendas: number;
}

// Los campos que el revisor puede reescribir en un producto (cuerpo del PATCH).
// Todos opcionales: se manda solo lo que cambio. `personaje` admite `null` para
// desligar un producto de su franquicia; `atributos` reemplaza el mapa entero.
export interface ProductoEditable {
  nombre?: string;
  descripcion?: string | null;
  marca?: string | null;
  nivel?: Nivel;
  personaje?: string | null;
  imagen_url?: string | null;
  unidad_base?: UnidadBase;
  unidades_por_empaque?: number;
  atributos?: Record<string, unknown>;
  quality_score?: number;
  es_propio?: boolean;
}

// El cuerpo de la reclasificacion: mover un producto bajo otro concepto.
export interface ReclasificarProducto {
  concepto: string;
}

// Los filtros del buscador de productos (`GET /v1/catalogo/productos`), tal como
// la SPA los pinta. Todos opcionales: sin filtros trae la primera pagina.
export interface FiltrosProductos {
  concepto?: string;
  nivel?: Nivel;
  personaje?: string;
  con_personaje?: boolean;
  busqueda?: string;
  con_precio?: boolean;
  con_ofertas?: boolean;
  pagina?: number;
  por_pagina?: number;
}

// El sobre paginado que devuelve la busqueda de productos. Los items ya vienen
// en la forma de detalle (`_producto_publico`), con concepto/unidad/empaque.
export interface PaginaProductos {
  total: number;
  pagina: number;
  por_pagina: number;
  productos: ProductoCatalogoDetalle[];
}

// Un personaje del catalogo, con cuantos productos lo llevan y —opcional— bajo
// que conceptos aparece. Lo consume el catalogo de personajes de la SPA (P4c) y
// el refactor de `empezar` (P4b).
export interface Personaje {
  nombre: string;
  productos: number;
  conceptos?: string[];
}

export interface ConceptoCatalogo {
  codigo: string;
  nombre_canonico: string;
  sinonimos: string[];
  categoria: string;
  tipo_item: TipoItem;
  // `discriminantes` filtra candidatos; `descriptivos` solo se le muestra al
  // acudiente. Que un atributo este en las dos listas es imposible por
  // restriccion de la base.
  atributos_discriminantes: string[];
  atributos_descriptivos: string[];
  admite_personaje: boolean;
  frecuencia_demanda: number;
  productos: ProductoCatalogo[];
}

export interface ResumenCatalogo {
  conceptos: number;
  productos: number;
  conceptos_con_tres_niveles: number;
  conceptos_sin_producto: number;
  productos_con_foto: number;
  tiendas: number;
  productos_sin_revisar: number;
}

export interface Catalogo {
  resumen: ResumenCatalogo;
  tiendas: TiendaCatalogo[];
  conceptos: ConceptoCatalogo[];
}

// ------------------------------------------------- Colegios y listas oficiales
//
// La entrada (a) del §2 del contrato pide elegir `colegio_id` y `grado`, pero
// el documento no dice de donde sale ese catalogo de colegios. Se asume una
// lectura publica, porque sin ella esa entrada no se puede pintar.

export interface Colegio {
  colegio_id: string;
  nombre: string;
  // El DANE del aliado (`null` si no lo cargo). El buscador de `/empezar` lo casa
  // contra el directorio de Bogota: si el DANE elegido en el directorio es el de
  // un aliado, el hijo se reconduce por `colegio_id` en vez de nacer como colegio
  // nuevo del directorio (que derivaria otro id y duplicaria el colegio).
  dane: string | null;
  // De que fichero del corpus salio la lista. Se expone porque el §2.2 del
  // contrato convierte la atribucion colegio-lista en un bloqueante de
  // correccion de esta ruta: el acudiente no puede detectar el error, asi que
  // lo menos que se puede hacer es mostrar contra que se esta comparando.
  fuente: string;
  atribucion_dudosa: boolean;
  // El logo del colegio aliado, tal como lo sirve identidad (`/v1/colegios`).
  // `null` cuando el colegio no cargo marca. Se lleva hasta aca para que el
  // selector pueda pintar la insignia del aliado sin una segunda lectura.
  logo_url: string | null;
  // Solo los grados con al menos una lista REVISADA (verificada). El selector
  // deriva de aqui: un colegio sin grados revisados no se puede elegir todavia.
  grados: string[];
  // Derivado de `grados.length > 0`: un colegio es "aliado" en cuanto tiene su
  // primer grado verificado. Es la misma condicion que el filtro del selector,
  // expuesta para que la pantalla no la recalcule.
  es_partner?: boolean;
}

export interface ItemListaOficial {
  orden: number;
  texto_original: string;
  texto_generico: string | null;
  cantidad: number;
  categoria: string | null;
  tipo_item: TipoItem;
  modo_adquisicion: string;
  libro?: {
    titulo: string;
    autor: string | null;
    editorial: string | null;
    periodo: string | null;
  };
}

/**
 * Lo que una persona tiene que decidir de una lista ya revisada
 * (`GET /v1/admin/listas/{version_id}/avisos`). Sale del mismo calculo que arma
 * los kits, asi que lo que se avisa es lo que le paso al kit.
 */
interface AvisoBase {
  item_id: string;
  orden: number;
  texto: string;
  concepto_codigo: string | null;
  concepto_nombre: string | null;
  /** La clave con que se descarta (`repetido:61`, `revisar:forma`, `sin_producto`). */
  clave: string;
}

export type AvisoLista =
  | (AvisoBase & { tipo: "posible_repetido"; repite_a: number; texto_repetido: string | null })
  | (AvisoBase & { tipo: "revisar_atributo"; atributo: string })
  | (AvisoBase & { tipo: "sin_producto"; exige: Record<string, unknown> });

export interface ListaOficial {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  version: number;
  // El id de la version vigente, para construir la URL del PDF de origen
  // (`/api/listas/{version_id}/documento`). Opcional: una lista sembrada/CLI
  // no tiene evidencia adjunta y el consumidor debe tolerar su ausencia.
  version_id?: string;
  items: ItemListaOficial[];
}

// ------------------------------------------------ Listas de admin (P1/P2)
//
// La entrada del indice `/v1/admin/listas` (region de trabajo del revisor):
// una version de lista importada por inteligencia, con lo que la cola necesita
// para priorizar —si ya se reviso, que numero de version es y cuantos items
// trae—. `numero` es el correlativo de version que P1 devuelve; `items` es un
// conteo, no el arreglo (ese vive en el detalle). ASUMIDO igual que el resto
// del fichero: se reconcilia con lo que P1 realmente sirve, en el borde HTTP.
export interface VersionListaAdmin {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  revisada: boolean;
  items: number;
  // De donde vino la version, para que la cola distinga los dos ingresos:
  // 'onboarding' (el colegio la envio o un administrador la subio) y
  // 'sugerencia_padre' (un acudiente la subio y espera su kit). `null` cuando
  // la version no nacio de una importacion con contexto (p.ej. sembrada).
  procedencia: ProcedenciaVersion | null;
  // Si hay un acudiente detras a quien avisar al aprobar. Nunca el correo: solo
  // el hecho de que exista una referencia (la PII vive en identidad).
  tiene_contacto: boolean;
  // El nombre del colegio NUEVO que el acudiente escribio/eligio, cuando el
  // colegio aun no existe en Tukit y por eso no tiene fila en `colegio` que le
  // de nombre. `null` para un colegio aliado (su nombre ya se resuelve por id).
  colegio_nombre: string | null;
}

// Los dos ingresos de una lista a la cola de revision. Es el `origen` de la
// `tarea_importacion` que produjo la version, acotado a los valores que la cola
// sabe pintar.
export type ProcedenciaVersion = "onboarding" | "sugerencia_padre";

// Los filtros del indice de versiones del revisor (`GET /v1/admin/listas`).
// Todos opcionales: sin filtros trae todas las versiones vigentes. `revisada`
// separa lo curado de lo pendiente; los demas acotan por colegio, grado o ano.
export interface FiltrosListasAdmin {
  revisada?: boolean;
  colegio_id?: string;
  grado?: string;
  anio_lectivo?: number;
}

// Un renglon editable de la lista, tal como el revisor lo escribe de vuelta.
// Es el cuerpo de `PATCH .../items/{item_id}` (editar) y de `POST .../items`
// (agregar) del `admin_http.py`, con todos los campos que `_valores_de_renglon`
// acepta. En una edicion todos son opcionales (se manda solo lo que cambio);
// en un alta, `texto_original` es lo unico que el backend exige. `concepto` es
// el CODIGO del concepto (C001, ...) que `_concepto_id` resuelve; `null`
// desliga el renglon y lo manda a revision (invariante del modelo). `atributos`
// reemplaza el mapa entero.
export interface ItemListaEditable {
  texto_original?: string;
  cantidad?: number;
  unidad?: UnidadBase | null;
  tipo_item?: TipoItem | null;
  modo_adquisicion?: ModoAdquisicion | null;
  concepto?: string | null;
  instruccion_colegio?: string | null;
  url_externa?: string | null;
  atributos?: Record<string, unknown>;
  requiere_revision?: boolean;
}

// Un renglon de una version tal como lo sirve la region 3 del revisor
// (`GET /v1/admin/listas/{version_id}/revision`, `_item_publico`). El backend
// anida el concepto en `{codigo, nombre}`; aca se aplana a
// `concepto_codigo`/`concepto_nombre` (ambos `null` cuando el renglon no tiene
// concepto y va a revision) para que la tabla del revisor no desestructure en
// cada celda.
export interface ItemRevision {
  id: string;
  orden: number;
  texto_original: string;
  cantidad: number;
  unidad: UnidadBase | null;
  tipo_item: TipoItem;
  modo_adquisicion: ModoAdquisicion | null;
  instruccion_colegio: string | null;
  url_externa: string | null;
  // Lo CURADO por el revisor: manda sobre lo leido del texto, y el valor `*`
  // (`NO_EXIGIR`) quita un atributo leido.
  atributos: Record<string, unknown>;
  requiere_revision: boolean;
  concepto_codigo: string | null;
  concepto_nombre: string | null;
  // Lo que la ruta rapida le exigiria al renglon (`_lo_que_se_exige`): las
  // claves curables (discriminantes del concepto asignado), lo leido del texto
  // con la misma regla de `_renglon_resuelto`, el resultado con la curaduria
  // encima y lo que el texto nombra con varios valores (no se exige). Vacios
  // si el renglon no tiene concepto o el concepto no filtra por atributos.
  atributos_discriminantes: string[];
  atributos_leidos: Record<string, unknown>;
  atributos_exigidos: Record<string, unknown>;
  atributos_por_revisar: string[];
  // Lo leido que el texto no dijo sino que se dedujo: hoy solo `unidades`
  // ("mas de uno" por `caja de...` o un plural). Si ningun juego cumple, la
  // ruta rapida lo suelta y vale la pieza suelta.
  atributos_deducidos: string[];
}

// Una propuesta de producto pendiente para un renglon, tal como la sirve la
// region 4 (`propuestas` de `ver_revision`). El precio ya viene en pesos
// enteros (el backend divide `precio_centavos` entre 100) y admite `null`
// ("no se conoce el precio", §1.4). `concepto` conserva la forma cruda del
// backend: el concepto ya decidido (`{codigo, nombre}`) o el que el modelo
// sugirio sin confirmar (`{sugerido}`).
export interface PropuestaRevision {
  id: string;
  texto_origen: string;
  // El renglón al que pertenece (`item_lista_oficial.id`). Llave 1:1 para colgar
  // los candidatos: `texto_origen` se repite cuando la lista pide dos renglones
  // iguales. `null` en propuestas viejas anteriores al vínculo.
  item_id: string | null;
  nombre: string;
  marca: string | null;
  imagen_url: string | null;
  precio: number | null;
  nivel_sugerido: Nivel | null;
  puntaje: number;
  concepto: { codigo: string; nombre: string } | { sugerido: string | null };
}

// ------------------------------------------- Curaduria del catalogo (P4c bis)
//
// La cola de curaduria PROACTIVA: propuestas de producto que el personal encola
// para llenar huecos del catalogo, ANTES de que un acudiente pregunte. Es un
// eje distinto de la revision de listas de colegio (esa vive en RevisionLista):
// aqui no hay version de lista detras, solo un concepto y una tienda.
//
// `PropuestaCola` es la fila de `GET /v1/admin/catalogo/propuestas`. El precio
// ya viene en pesos enteros (el backend divide `precio_centavos` entre 100) y
// admite `null` ("no se conoce el precio", §1.4). `concepto` conserva la forma
// cruda del backend: el concepto ya decidido (`{codigo, nombre}`) o el que el
// modelo sugirio sin confirmar (`{sugerido}`), igual que `PropuestaRevision`.
export interface PropuestaCola {
  id: string;
  id_corto: string;
  texto_origen: string;
  nombre: string;
  marca: string | null;
  imagen_url: string | null;
  precio: number | null;
  nivel_sugerido: string | null;
  puntaje: number;
  concepto: { codigo: string; nombre: string } | { sugerido: string | null };
  origen: string;
  /** Atributos que quien propuso verificó contra la ficha de la tienda ({} si no hay). */
  atributos_verificados?: Record<string, unknown>;
  /** Los atributos con que nace el producto si se aprueba sin corregir nada. */
  atributos_al_aprobar?: Record<string, unknown>;
}

// Un candidato de tienda tal como lo sirve `GET .../tiendas/{slug}/buscar`
// (envuelve `tiendas.buscar`). El precio ya viene en pesos enteros; a diferencia
// de `PropuestaCola` nunca es nulo porque un candidato sin precio no se lista.
// `especificaciones` es el mapa crudo que la tienda expone (siempre texto).
export interface CandidatoTienda {
  slug: string;
  sku: string;
  nombre: string;
  precio: number;
  marca: string | null;
  ean: string | null;
  url: string;
  imagen_url: string | null;
  disponible: boolean;
  especificaciones: Record<string, string>;
}

// El cuerpo del alta de un util (`POST .../propuestas/util`). El servidor
// re-busca por `(slug, sku)` para no confiar en un precio que el navegador
// pudo alterar; `consulta` es la misma con la que se encontro el candidato.
export interface AltaUtil {
  concepto: string;
  slug: string;
  sku: string;
  consulta: string;
  nivel: string;
}

// El cuerpo para crear un concepto nuevo (`POST .../catalogo/conceptos`). El
// `codigo` NO viaja: lo autogenera el backend (el siguiente `C0NN` libre). Es el
// otro brazo del bucle de curacion —cuando un renglon no empareja con nada, el
// revisor crea el concepto y luego le agrega productos—, para que la BD crezca
// revisando. `sinonimos` ayuda al matcher a reconocerlo en la proxima lista;
// `tipo_item` cae a "util" (lo comprable) si no se dice.
export interface CrearConcepto {
  nombre_canonico: string;
  categoria: string;
  sinonimos?: string;
  tipo_item?: string;
  admite_personaje?: boolean;
  // Los dos papeles del atributo: el discriminante FILTRA productos (un
  // cuaderno cuadriculado no pasa por uno rayado) y el descriptivo solo
  // informa. Un nombre no puede estar en las dos listas.
  atributos_discriminantes?: string[];
  atributos_descriptivos?: string[];
}

// La respuesta de crear un concepto: el codigo autogenerado con que ya se le
// pueden encolar productos.
export interface ConceptoCreado {
  codigo: string;
  nombre_canonico: string;
  categoria: string;
  tipo_item: string;
  atributos_discriminantes?: string[];
  atributos_descriptivos?: string[];
}

// El cuerpo del alta de un util escrito a mano (`POST .../propuestas/util-manual`).
// Para lo que la busqueda en vivo no encuentra: la Oferta se arma de estos
// campos, no se re-busca. `precio` es entero en PESOS y > 0 (el backend lo pasa
// a centavos). `sku` es opcional; sin el, el backend deriva uno estable de
// (slug, nombre). `slug` puede ser cualquier tienda registrada.
export interface AltaUtilManual {
  concepto: string;
  nombre: string;
  precio: number;
  slug: string;
  sku?: string;
  url?: string;
  marca?: string;
  nivel: string;
}

// El cuerpo del alta de un libro (`POST .../propuestas/libro`). Manual: el
// personal copia ISBN/titulo/precio de Buscalibre (que no expone busqueda en
// vivo). `precio` es entero en PESOS y > 0; el backend lo pasa a centavos.
export interface AltaLibro {
  concepto: string;
  isbn: string;
  titulo: string;
  precio: number;
  slug: string;
  nivel: string;
}

// El cuerpo de la aprobacion (`POST .../propuestas/{id}/aprobar`): la persona
// decide el nivel al aprobar, no al encolar (los dos pasos van separados).
//
// Ademas del nivel, la cola puede corregir a mano el producto ANTES de que
// nazca: nombre, marca, imagen y atributos. Todos son OPCIONALES; una clave
// ausente conserva el valor que la propuesta traia (o lo que se derivo del
// nombre/ficha), asi que aprobar con solo `{nivel}` es identico a como era.
// `marca`/`imagen_url`/`personaje` en `null` guardan "sin dato". `atributos`
// REEMPLAZA el mapa entero (misma semantica que el editor de catalogo), no lo
// fusiona. Es el unico momento de editarlos aca: despues, el producto ya
// existe y se corrige por el PATCH del editor.
export interface AprobarPropuesta {
  nivel: string;
  nombre?: string;
  marca?: string | null;
  imagen_url?: string | null;
  personaje?: string | null;
  atributos?: Record<string, string | number | boolean>;
}

// El cuerpo del rechazo (`POST /v1/admin/propuestas/{id}/rechazar`, ruta ya
// existente). `no_surtir` manda el concepto a 'no_comprar' en vez de solo
// descartar el candidato.
export interface RechazarPropuesta {
  motivo?: string;
  no_surtir?: boolean;
}

// La respuesta de un alta: la propuesta cae en la cola (`estado: "pendiente"`),
// NO se aprueba en el acto. `id_corto` es el prefijo de 8 que la cola muestra.
export interface PropuestaEncolada {
  id: string;
  id_corto: string;
  estado: string;
}

// La vista completa de la region 3/4: la cabecera de la version, sus renglones
// y las propuestas pendientes. Es la forma de
// `GET /v1/admin/listas/{version_id}/revision`.
export interface RevisionLista {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  revisada: boolean;
  items: ItemRevision[];
  propuestas: PropuestaRevision[];
  // Los datos del colegio NUEVO que se dara de alta al aprobar, cuando la lista
  // la subio un acudiente para un colegio que aun no existe en Tukit (lo eligio
  // del directorio de Bogota o lo escribio). `null` cuando es de un colegio ya
  // aliado: no hay identidad que crear ni perfil que completar. El revisor
  // completa estos campos con `completarColegioDeVersion` antes de aprobar.
  colegio_datos: DatosColegioNuevo | null;
}

// El perfil del colegio nuevo que viaja en `colegio_datos` de una version en la
// cola. `nombre` y `dane` los fija la subida (el `dane` deriva el `colegio_id`,
// no se edita); el resto los completa el revisor. Todos son datos de la
// INSTITUCION, no del menor: no son PII.
export interface DatosColegioNuevo {
  nombre?: string | null;
  dane?: string | null;
  logo_url?: string | null;
  sitio_web?: string | null;
  direccion?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
}

// Los campos del colegio nuevo que el revisor puede completar antes de aprobar
// (cuerpo del `PATCH /v1/admin/listas/{version_id}/colegio`). Se manda solo lo
// que cambio; el backend hace merge sobre `colegio_datos`. NO incluye `dane`:
// cambiarlo cambiaria el `colegio_id` derivado y desligaria la lista del colegio.
export interface ColegioNuevoEditable {
  nombre?: string;
  logo_url?: string;
  sitio_web?: string;
  direccion?: string;
  contacto_nombre?: string;
  contacto_email?: string;
  contacto_telefono?: string;
}

// Una sede de un colegio, tal como la sirve el detalle de identidad
// (`GET /v1/colegios/{id}`).
export interface SedeColegio {
  sede_id: string;
  nombre: string;
}

// El detalle de un colegio, mas rico que el `Colegio` del selector: trae los
// datos de identidad/marca que la pantalla de administracion edita. Es la forma
// de `GET /v1/colegios/{id}` y la respuesta de `PATCH /v1/colegios/{id}`. Los
// campos de contacto son del colegio (secretaria academica, no un menor) y
// pueden faltar (`null`).
export interface ColegioDetalle {
  colegio_id: string;
  nombre: string;
  // El codigo DANE del DUEB, la llave del directorio oficial. Puede faltar
  // (`null`) en colegios sembrados; el admin lo completa para leer la ficha.
  dane: string | null;
  logo_url: string | null;
  sitio_web: string | null;
  contacto_nombre: string | null;
  contacto_email: string | null;
  contacto_telefono: string | null;
  direccion: string | null;
  sedes: SedeColegio[];
}

// Los campos que el administrador puede reescribir de la identidad de un
// colegio (cuerpo del `PATCH /v1/colegios/{id}`). Todos opcionales: se manda
// solo lo que cambio. `null` limpia el campo. NO incluye `nombre` ni `sedes`:
// esos no se editan por esta ruta.
export interface ColegioEditable {
  // El DANE si es editable por esta ruta (a diferencia del nombre): en identidad
  // el `colegio_id` ya esta fijado y no se re-deriva del DANE, asi que
  // completarlo cuando falta es seguro y habilita leer su ficha del directorio.
  dane?: string | null;
  logo_url?: string | null;
  sitio_web?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
}

// A que colegio va una lista que el staff sube desde la cola
// (`POST /v1/admin/onboarding`). Las mismas tres formas que la subida del
// acudiente: un colegio que Tukit ya conoce, una entrada del directorio de
// Bogota (el colegio nace al aprobar, con el id derivado del DANE) o un nombre
// escrito a mano porque no estaba en el directorio.
export type ColegioDesignado =
  | { colegio_id: string }
  | { colegio_dane: string; colegio_nombre: string }
  | { colegio_nombre: string };

// La ficha COMPLETA del directorio DUEB para el detalle del colegio en el admin
// (`GET /v1/directorio/{dane}`). Es un superconjunto de `DatosColegioNuevo`:
// repite sus 7 campos con el mismo nombre y significado y AGREGA sector,
// localidad, rector y las listas completas de telefonos/correos. Se mantiene
// aparte a proposito: `DatosColegioNuevo` es la forma del ALTA (onboarding y
// poller) y no debe crecer con campos que solo la ficha usa.
export interface DirectorioColegio {
  dane?: string | null;
  nombre?: string | null;
  direccion?: string | null;
  sitio_web?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
  sector?: string | null;
  localidad?: string | null;
  rector?: string | null;
  telefonos?: string[];
  correos?: string[];
}

// Una sugerencia de lista en el backlog del administrador
// (`GET /v1/admin/sugerencias`), derivada de las `tarea_importacion` con
// origen 'sugerencia_padre'. La UNICA traza al acudiente es
// `contacto_referencia` (el usuario_id que identidad emite): NUNCA correo ni
// telefono —esa PII vive solo en identidad y no cruza aca—. `tiene_documento`
// dice si el padre adjunto evidencia sin exponer el PDF.
export interface Sugerencia {
  tarea_id: string;
  estado: string;
  colegio_id: string | null;
  grado: string | null;
  anio_lectivo: number | null;
  contacto_referencia: string | null;
  tiene_documento: boolean;
}

export const NIVELES: readonly Nivel[] = ["economico", "confiable", "premium"];

export const ETIQUETA_NIVEL: Record<Nivel, string> = {
  economico: "Economico",
  confiable: "Confiable",
  premium: "Premium",
};

export const ORDEN_NIVEL: Record<Nivel, number> = {
  economico: 0,
  confiable: 1,
  premium: 2,
};

// El precio honesto de un producto es el mas barato entre las tiendas que lo
// venden, porque es el que el kit va a pagar. Mostrar otro seria prometer de
// mas. Es la misma definicion que usa la consulta de `vista.py`.
export function precioMasBarato(producto: ProductoCatalogo): Dinero | null {
  const precios = producto.ofertas
    .map((o) => o.precio)
    .filter((p): p is number => typeof p === "number");
  return precios.length > 0 ? Math.min(...precios) : null;
}

export function unidadesDeEmpaque(producto: ProductoCatalogo): {
  unidad: UnidadBase;
  cantidad: number;
} {
  const declaradas = producto.atributos["cantidades_declaradas"];
  if (Array.isArray(declaradas)) {
    for (const token of declaradas) {
      const m = /^(\d+):unidades$/.exec(String(token));
      if (m?.[1]) return { unidad: "unidad", cantidad: Number(m[1]) };
    }
  }
  return { unidad: "unidad", cantidad: 1 };
}

export type CoberturaConcepto = "sin_productos" | "parcial" | "tres_niveles";

export function coberturaDe(concepto: ConceptoCatalogo): CoberturaConcepto {
  if (concepto.productos.length === 0) return "sin_productos";
  const niveles = new Set(concepto.productos.map((p) => p.nivel));
  return niveles.size >= 3 ? "tres_niveles" : "parcial";
}

// ------------------------------------------------- Atributos tipados del editor
//
// El editor de productos escribe cada atributo como texto (una caja de input),
// pero la base los guarda TIPADOS (`hojas: 80` int, `deposito: true` bool,
// `rayado: "cuadriculado"` str). Sin este paso, guardar degrada `80` a `"80"`.
// El tipo lo fija el cliente aqui; el backend solo endurece la guarda (rechaza
// listas/dicts). Escalares nada mas: str/int/float/bool.
//
// Regla de numero: se convierte solo si el texto redondea al mismo string
// (`String(n) === texto`). Asi `"80"`→`80` pero `"007"` (un codigo con ceros a
// la izquierda) o `"1e3"` se quedan como texto, que es lo que la persona quiso.
export function inferirTipoAtributo(texto: string): string | number | boolean {
  const limpio = texto.trim();
  if (limpio === "true") return true;
  if (limpio === "false") return false;
  // Entero o decimal simple; nada de notacion cientifica ni signos raros.
  if (/^-?\d+(\.\d+)?$/.test(limpio)) {
    const n = Number(limpio);
    if (Number.isFinite(n) && String(n) === limpio) return n;
  }
  return texto;
}

// Convierte los pares clave/valor del editor en el mapa de atributos tipado que
// viaja en el PATCH. Descarta la clave vacia y el valor `""`: un atributo sin
// valor NO se afirma (consistente con `extraer_atributos` del backend, "ausente
// antes que inventado", y con la guarda `atributos_invalido"). La ultima
// ocurrencia de una clave repetida gana.
export function serializarAtributos(
  pares: { clave: string; valor: string }[],
): Record<string, string | number | boolean> {
  const salida: Record<string, string | number | boolean> = {};
  for (const { clave, valor } of pares) {
    const k = clave.trim();
    if (!k || valor === "") continue;
    salida[k] = inferirTipoAtributo(valor);
  }
  return salida;
}
