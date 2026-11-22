"use client";

import { useMemo, useState } from "react";
import { Trash2 } from "lucide-react";
import { NIVELES, ETIQUETA_NIVEL, serializarAtributos } from "@tukit/contrato";
import type { Nivel, ProductoCatalogoDetalle, ProductoEditable, UnidadBase } from "@tukit/contrato";
import {
  editarProducto,
  eliminarProducto,
  reclasificarProducto,
  FalloCatalogo,
} from "@/lib/api-catalogo";
import {
  conCampo,
  conValor,
  filasDeAtributos,
  pareceUrl,
  type ParAtributo,
} from "@/lib/atributos-editor";
import GrupoAtributos from "./GrupoAtributos";
import PanelReclasificar, { type OpcionConcepto } from "./PanelReclasificar";
import Desplegable from "./Desplegable";
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

  const conceptoDelProducto = conceptos.find((c) => c.codigo === producto.concepto.codigo);
  const gruposIniciales = useMemo(
    () =>
      filasDeAtributos(
        producto.atributos,
        conceptoDelProducto?.atributos_discriminantes ?? [],
        conceptoDelProducto?.atributos_descriptivos ?? [],
      ),
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

  const editarLibre = (indice: number, campo: keyof ParAtributo, valor: string) =>
    setLibres((prev) => conCampo(prev, indice, campo, valor));

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

        <span className={styles.subtitulo}>Re-etiquetar</span>

        <div className={styles.campo}>
          <label htmlFor="ed-marca">Marca</label>
          <input id="ed-marca" value={marca} onChange={(e) => setMarca(e.target.value)} />
        </div>

        <div className={styles.campo}>
          <label htmlFor="ed-nivel">Nivel</label>
          <Desplegable
            id="ed-nivel"
            tamano="compacto"
            opciones={NIVELES.map((n) => ({ valor: n, texto: ETIQUETA_NIVEL[n] }))}
            valor={nivel}
            onCambio={(v) => setNivel(v as Nivel)}
          />
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

        <span className={styles.subtitulo}>Empaque y calidad</span>

        <div className={styles.campo}>
          <label htmlFor="ed-unidad">Unidad base</label>
          <Desplegable
            id="ed-unidad"
            tamano="compacto"
            opciones={UNIDADES.map((u) => ({ valor: u, texto: u }))}
            valor={unidadBase}
            onCambio={(v) => setUnidadBase(v as UnidadBase)}
          />
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

        <span className={styles.subtitulo}>Atributos</span>

        <GrupoAtributos
          titulo="Filtra la búsqueda"
          nota="estos atributos deciden qué candidatos entran a un kit."
          filas={discriminantes}
          onEditar={(i, valor) => setDiscriminantes((prev) => conValor(prev, i, valor))}
        />
        <GrupoAtributos
          titulo="Solo informativo"
          nota="se le muestran al acudiente pero no filtran."
          filas={descriptivos}
          onEditar={(i, valor) => setDescriptivos((prev) => conValor(prev, i, valor))}
        />

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
