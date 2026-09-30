// Editor de un producto del catálogo (P4c): CRUD de TODOS los campos
// editables, gestión de imagen por URL con vista previa, re-etiqueta
// (nivel/personaje/marca/atributos son el mismo PATCH) y baja suave. Embebe el
// panel de re-clasificación (efecto distinto: re-embedding) y el borrado
// guardado.
//
// Escribe a través de los Route Handlers vía `api-catalogo`; el mensaje de
// error que muestra es el del backend (nivel_invalido, empaque_invalido,
// quality_score_invalido, campo_no_editable…), nunca uno inventado aquí.

"use client";

import { useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { Trash2 } from "lucide-react";
import { NIVELES, ETIQUETA_NIVEL, serializarAtributos } from "@tukit/contrato";
import type {
  Nivel,
  ProductoCatalogoDetalle,
  ProductoEditable,
  UnidadBase,
} from "@tukit/contrato";
import {
  editarProducto,
  eliminarProducto,
  reclasificarProducto,
  FalloCatalogo,
} from "@/lib/api-catalogo";
import { filasDeAtributos, type ParAtributo } from "@/lib/atributos-editor";
import PanelReclasificar, { type OpcionConcepto } from "./PanelReclasificar";
import styles from "./CatalogoSpa.module.css";

const UNIDADES: readonly UnidadBase[] = [
  "unidad",
  "hoja",
  "pliego",
  "metro",
  "gramo",
  "mililitro",
];

interface Props {
  producto: ProductoCatalogoDetalle;
  conceptos: OpcionConcepto[];
  personajes: string[];
  onGuardado: (producto: ProductoCatalogoDetalle) => void;
  onEliminado: (sku: string) => void;
  onCerrar: () => void;
}

function pareceUrl(texto: string): boolean {
  if (!texto.trim()) return true; // vacío = sin imagen, válido
  try {
    const u = new URL(texto);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

export default function EditorProducto({
  producto,
  conceptos,
  personajes,
  onGuardado,
  onEliminado,
  onCerrar,
}: Props) {
  const [nombre, setNombre] = useState(producto.nombre);
  const [descripcion, setDescripcion] = useState(producto.descripcion ?? "");
  const [marca, setMarca] = useState(producto.marca ?? "");
  const [nivel, setNivel] = useState<Nivel>(producto.nivel);
  const [personaje, setPersonaje] = useState(producto.personaje ?? "");
  const [imagenUrl, setImagenUrl] = useState(producto.imagen_url ?? "");
  const [unidadBase, setUnidadBase] = useState<UnidadBase>(producto.unidad_base);
  const [empaque, setEmpaque] = useState(String(producto.unidades_por_empaque));
  const [quality, setQuality] = useState(String(producto.quality_score));
  const [esPropio, setEsPropio] = useState(producto.es_propio);

  // El esquema de atributos sale del concepto del producto: se pre-pueblan
  // TODAS las claves que declara (discriminantes + descriptivos), no solo las
  // que el producto trae. Las que el producto tiene pero el concepto no declara
  // caen en "libres" para no perderlas. Si el concepto no viaja (no está en la
  // lista), se cae al comportamiento previo: solo las claves del producto.
  const conceptoDelProducto = conceptos.find((c) => c.codigo === producto.concepto.codigo);
  const gruposIniciales = useMemo(
    () =>
      filasDeAtributos(
        producto.atributos,
        conceptoDelProducto?.atributos_discriminantes ?? [],
        conceptoDelProducto?.atributos_descriptivos ?? [],
      ),
    // Solo depende del producto abierto; el padre remonta con `key={sku}`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const [discriminantes, setDiscriminantes] = useState<ParAtributo[]>(
    gruposIniciales.discriminantes,
  );
  const [descriptivos, setDescriptivos] = useState<ParAtributo[]>(gruposIniciales.descriptivos);
  const [libres, setLibres] = useState<ParAtributo[]>(gruposIniciales.libres);

  const [guardando, setGuardando] = useState(false);
  const [reclasificando, setReclasificando] = useState(false);
  const [eliminando, setEliminando] = useState(false);
  const [confirmarBaja, setConfirmarBaja] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  // No hay efecto de reinicio: el padre monta este componente con
  // `key={sku}`, así que cambiar de producto lo remonta entero y todos los
  // `useState` arrancan de su valor inicial. Es el patrón recomendado sobre
  // sincronizar estado desde un efecto.

  const urlValida = useMemo(() => pareceUrl(imagenUrl), [imagenUrl]);
  const empaqueNum = Number(empaque);
  const empaqueValido = Number.isInteger(empaqueNum) && empaqueNum > 0;
  const qualityNum = Number(quality);
  const qualityValido = !Number.isNaN(qualityNum) && qualityNum >= 0 && qualityNum <= 1;

  const puedeGuardar = urlValida && empaqueValido && qualityValido && nombre.trim().length > 0;

  async function guardar() {
    setError(null);
    setExito(null);
    if (!puedeGuardar) {
      setError("Revisá los campos marcados antes de guardar.");
      return;
    }

    // El mapa de atributos se reemplaza entero (contrato: `atributos` reemplaza
    // el mapa). `serializarAtributos` tipa cada valor (`"80"`→`80`,
    // `"true"`→`true`) y descarta las filas vacías: una clave sin valor NO se
    // afirma (consistente con la guarda `atributos_invalido` del backend).
    const mapaAtributos = serializarAtributos([...discriminantes, ...descriptivos, ...libres]);

    const cambios: ProductoEditable = {
      nombre: nombre.trim(),
      descripcion: descripcion.trim() ? descripcion.trim() : null,
      marca: marca.trim() ? marca.trim() : null,
      nivel,
      personaje: personaje.trim() ? personaje.trim() : null,
      imagen_url: imagenUrl.trim() ? imagenUrl.trim() : null,
      unidad_base: unidadBase,
      unidades_por_empaque: empaqueNum,
      quality_score: qualityNum,
      es_propio: esPropio,
      atributos: mapaAtributos,
    };

    setGuardando(true);
    try {
      const actualizado = await editarProducto(producto.sku, cambios);
      setExito("Cambios guardados.");
      onGuardado(actualizado);
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos guardar los cambios.");
    } finally {
      setGuardando(false);
    }
  }

  async function reclasificar(concepto: string) {
    setError(null);
    setExito(null);
    setReclasificando(true);
    try {
      const actualizado = await reclasificarProducto(producto.sku, concepto);
      setExito("Producto re-clasificado. Se recalculará el embedding.");
      onGuardado(actualizado);
    } catch (causa) {
      setError(
        causa instanceof FalloCatalogo ? causa.message : "No pudimos re-clasificar el producto.",
      );
    } finally {
      setReclasificando(false);
    }
  }

  async function darDeBaja() {
    setError(null);
    setExito(null);
    setEliminando(true);
    try {
      await eliminarProducto(producto.sku);
      onEliminado(producto.sku);
    } catch (causa) {
      setError(causa instanceof FalloCatalogo ? causa.message : "No pudimos dar de baja el producto.");
      setEliminando(false);
    }
  }

  // Los grupos declarados (discriminantes/descriptivos) solo editan el VALOR:
  // la clave la fija el concepto y no se toca. El grupo libre sí edita clave y
  // valor y permite quitar filas, como el editor plano anterior.
  function editarValor(
    set: Dispatch<SetStateAction<ParAtributo[]>>,
    indice: number,
    valor: string,
  ) {
    set((prev) => prev.map((p, i) => (i === indice ? { ...p, valor } : p)));
  }

  function editarLibre(indice: number, campo: keyof ParAtributo, valor: string) {
    setLibres((prev) => prev.map((p, i) => (i === indice ? { ...p, [campo]: valor } : p)));
  }

  // Un grupo declarado: cada fila muestra la clave (fija) y una caja de valor.
  function grupoDeclarado(
    titulo: string,
    nota: string,
    filas: ParAtributo[],
    set: Dispatch<SetStateAction<ParAtributo[]>>,
  ) {
    if (filas.length === 0) return null; // no se muestra encabezado de grupo vacío
    return (
      <div className={styles.atributos}>
        <span className={styles.ayuda}>
          <strong>{titulo}</strong> — {nota}
        </span>
        {filas.map((par, i) => (
          <div key={par.clave} className={styles.atributoFila}>
            <input aria-label="Clave" value={par.clave} readOnly disabled />
            <input
              aria-label={`Valor de ${par.clave}`}
              placeholder="(sin valor)"
              value={par.valor}
              onChange={(e) => editarValor(set, i, e.target.value)}
            />
          </div>
        ))}
      </div>
    );
  }

  return (
    <section className={styles.panel} aria-label={`Editar ${producto.nombre}`}>
      <header className={styles.panelCabecera}>
        <div>
          <h2>{producto.nombre}</h2>
          <span className={styles.panelSku}>{producto.sku}</span>
        </div>
        <button type="button" className={styles.secundario} onClick={onCerrar}>
          Cerrar
        </button>
      </header>

      {error && <p className={styles.error}>{error}</p>}
      {exito && <p className={styles.exito}>{exito}</p>}

      <div className={styles.rejilla}>
        <div className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor="ed-nombre">Nombre</label>
          <input
            id="ed-nombre"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
          />
          {nombre.trim().length === 0 && (
            <span className={`${styles.ayuda} ${styles.ayudaError}`}>
              El nombre no puede quedar vacío.
            </span>
          )}
        </div>

        <div className={`${styles.campo} ${styles.campoAncho}`}>
          <label htmlFor="ed-descripcion">Descripción</label>
          <textarea
            id="ed-descripcion"
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
          />
        </div>

        {/* Re-etiqueta: marca, nivel y personaje son el mismo PATCH. */}
        <span className={styles.subtitulo}>Re-etiquetar</span>

        <div className={styles.campo}>
          <label htmlFor="ed-marca">Marca</label>
          <input id="ed-marca" value={marca} onChange={(e) => setMarca(e.target.value)} />
        </div>

        <div className={styles.campo}>
          <label htmlFor="ed-nivel">Nivel</label>
          <select
            id="ed-nivel"
            value={nivel}
            onChange={(e) => setNivel(e.target.value as Nivel)}
          >
            {NIVELES.map((n) => (
              <option key={n} value={n}>
                {ETIQUETA_NIVEL[n]}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.campo}>
          <label htmlFor="ed-personaje">Personaje</label>
          <input
            id="ed-personaje"
            list="lista-personajes"
            value={personaje}
            onChange={(e) => setPersonaje(e.target.value)}
            placeholder="sin personaje"
          />
          <datalist id="lista-personajes">
            {personajes.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
          <span className={styles.ayuda}>Vacío = desliga el producto de su franquicia.</span>
        </div>

        {/* Imagen: URL + vista previa en vivo. Backend URL-only, sin subida. */}
        <span className={styles.subtitulo}>Imagen</span>
        <div className={styles.imagenBloque}>
          <div className={`${styles.campo} ${styles.imagenCampo}`}>
            <label htmlFor="ed-imagen">URL de la imagen</label>
            <input
              id="ed-imagen"
              value={imagenUrl}
              onChange={(e) => setImagenUrl(e.target.value)}
              placeholder="https://…"
            />
            {!urlValida && (
              <span className={`${styles.ayuda} ${styles.ayudaError}`}>
                Tiene que ser una URL http(s) válida.
              </span>
            )}
            <span className={styles.ayuda}>
              Solo por URL: no hay subida de archivos en el backend.
            </span>
          </div>
          {imagenUrl.trim() && urlValida ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className={styles.previa} src={imagenUrl} alt="Vista previa" />
          ) : (
            <span className={styles.previaVacia}>Sin imagen</span>
          )}
        </div>

        {/* Empaque y unidad: alimentan el precio por unidad. */}
        <span className={styles.subtitulo}>Empaque y calidad</span>

        <div className={styles.campo}>
          <label htmlFor="ed-unidad">Unidad base</label>
          <select
            id="ed-unidad"
            value={unidadBase}
            onChange={(e) => setUnidadBase(e.target.value as UnidadBase)}
          >
            {UNIDADES.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.campo}>
          <label htmlFor="ed-empaque">Unidades por empaque</label>
          <input
            id="ed-empaque"
            type="number"
            min={1}
            step={1}
            value={empaque}
            onChange={(e) => setEmpaque(e.target.value)}
          />
          {!empaqueValido && (
            <span className={`${styles.ayuda} ${styles.ayudaError}`}>
              Un entero mayor que 0.
            </span>
          )}
        </div>

        <div className={styles.campo}>
          <label htmlFor="ed-quality">Quality score (0–1)</label>
          <input
            id="ed-quality"
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={quality}
            onChange={(e) => setQuality(e.target.value)}
          />
          {!qualityValido && (
            <span className={`${styles.ayuda} ${styles.ayudaError}`}>
              Un número entre 0 y 1.
            </span>
          )}
        </div>

        <div className={styles.campo}>
          <label htmlFor="ed-propio">Producto propio</label>
          <label className={styles.bandera}>
            <input
              id="ed-propio"
              type="checkbox"
              checked={esPropio}
              onChange={(e) => setEsPropio(e.target.checked)}
            />
            Es un producto de Tukit
          </label>
        </div>

        {/* Atributos: pre-poblados por el concepto (todas sus claves), en dos
            grupos, más las claves libres que el producto ya trae. Una fila con
            valor vacío no afirma la clave (no se guarda). */}
        <span className={styles.subtitulo}>Atributos</span>

        {grupoDeclarado(
          "Filtra la búsqueda",
          "estos atributos deciden qué candidatos entran a un kit.",
          discriminantes,
          setDiscriminantes,
        )}
        {grupoDeclarado(
          "Solo informativo",
          "se le muestran al acudiente pero no filtran.",
          descriptivos,
          setDescriptivos,
        )}

        {/* Claves libres: las que el producto trae y el concepto no declara, más
            las que se agreguen a mano. Aquí sí se edita la clave y se quitan. */}
        <div className={styles.atributos}>
          {discriminantes.length === 0 && descriptivos.length === 0 && libres.length === 0 && (
            <span className={styles.ayuda}>Sin atributos. Agregá uno abajo.</span>
          )}
          {libres.length > 0 && (
            <span className={styles.ayuda}>
              <strong>Otros</strong> — claves que este concepto no declara.
            </span>
          )}
          {libres.map((par, i) => (
            <div key={i} className={styles.atributoFila}>
              <input
                aria-label="Clave"
                placeholder="clave"
                value={par.clave}
                onChange={(e) => editarLibre(i, "clave", e.target.value)}
              />
              <input
                aria-label="Valor"
                placeholder="valor"
                value={par.valor}
                onChange={(e) => editarLibre(i, "valor", e.target.value)}
              />
              <button
                type="button"
                className={styles.secundario}
                onClick={() => setLibres((prev) => prev.filter((_, j) => j !== i))}
                aria-label="Quitar atributo"
              >
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>
          ))}
          <button
            type="button"
            className={styles.secundario}
            style={{ alignSelf: "flex-start" }}
            onClick={() => setLibres((prev) => [...prev, { clave: "", valor: "" }])}
          >
            + Atributo
          </button>
        </div>

        {/* Solo lectura: identidad del producto que no se edita. */}
        <dl className={styles.datosSoloLectura}>
          <div>
            <dt>SKU</dt>
            <dd>{producto.sku}</dd>
          </div>
          <div>
            <dt>EAN</dt>
            <dd>{producto.ean ?? "—"}</dd>
          </div>
          <div>
            <dt>Concepto</dt>
            <dd>{producto.concepto.nombre}</dd>
          </div>
          <div>
            <dt>Tiendas</dt>
            <dd>{producto.tiendas}</dd>
          </div>
        </dl>

        {/* Re-clasificación: efecto distinto (re-embedding), acción aparte. */}
        <PanelReclasificar
          conceptos={conceptos}
          conceptoActual={producto.concepto.codigo}
          enProgreso={reclasificando}
          onReclasificar={reclasificar}
        />
      </div>

      <div className={styles.acciones}>
        <button
          type="button"
          className={styles.principal}
          disabled={guardando || !puedeGuardar}
          onClick={guardar}
        >
          {guardando ? "Guardando…" : "Guardar cambios"}
        </button>
        <span className={styles.separador} />
        {!confirmarBaja ? (
          <button
            type="button"
            className={styles.peligro}
            onClick={() => setConfirmarBaja(true)}
          >
            <Trash2 size={14} aria-hidden="true" /> Dar de baja
          </button>
        ) : null}
      </div>

      {confirmarBaja && (
        <div className={styles.confirmBaja}>
          <p>
            Dar de baja retira el producto del catálogo para todos los trabajos (queda inactivo,
            no se borra de la base). ¿Continuar?
          </p>
          <div className={styles.acciones} style={{ border: "none", padding: 0 }}>
            <button
              type="button"
              className={styles.peligro}
              disabled={eliminando}
              onClick={darDeBaja}
            >
              {eliminando ? "Dando de baja…" : "Sí, dar de baja"}
            </button>
            <button
              type="button"
              className={styles.secundario}
              disabled={eliminando}
              onClick={() => setConfirmarBaja(false)}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
