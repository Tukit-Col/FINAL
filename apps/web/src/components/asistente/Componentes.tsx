"use client";

import { CLAVES_PESO, ETIQUETA_PESO, formatearCop, textoDelta, type ClavePeso, type TarjetaProducto } from "./espec";
import estilos from "./Asistente.module.css";

export function TarjetaPersonaje({ nombre, imagen_url }: { nombre: string; imagen_url: string | null }) {
  return (
    <li className={`${estilos.tarjeta} ${estilos.personaje}`}>
      {imagen_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className={estilos.foto} src={imagen_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
      ) : (
        <span className={estilos.sinFoto} aria-hidden="true">
          {nombre.slice(0, 1).toUpperCase()}
        </span>
      )}
      <div>
        <p className={estilos.nombre}>{nombre}</p>
        <p className={estilos.ayuda}>Lo buscamos primero en los útiles de tu hijo.</p>
      </div>
    </li>
  );
}

export function SelectorPresupuesto({
  minimo,
  maximo,
  paso,
  valor,
  onCambio,
}: {
  minimo: number;
  maximo: number;
  paso: number;
  valor: number | null;
  onCambio: (valor: number | null) => void;
}) {
  const activo = valor !== null;
  return (
    <div className={estilos.tarjeta}>
      <label className={estilos.rotulo} htmlFor="asistente-tope">
        Cuánto quieres gastar como máximo por hijo
      </label>
      <p className={estilos.valor}>{activo ? formatearCop(valor) : "Sin tope"}</p>
      <input
        id="asistente-tope"
        className={estilos.rango}
        type="range"
        min={minimo}
        max={maximo}
        step={paso}
        value={activo ? valor : Math.round((minimo + maximo) / 2 / paso) * paso}
        onChange={(e) => onCambio(Number(e.target.value))}
      />
      <div className={estilos.acciones}>
        <button type="button" className={estilos.secundario} onClick={() => onCambio(null)} disabled={!activo}>
          No poner tope
        </button>
      </div>
    </div>
  );
}

export function Prioridades({
  orden,
  onCambio,
}: {
  orden: ClavePeso[];
  onCambio: (orden: ClavePeso[]) => void;
}) {
  function mover(indice: number, delta: -1 | 1) {
    const destino = indice + delta;
    if (destino < 0 || destino >= orden.length) return;
    const copia = [...orden];
    const [pieza] = copia.splice(indice, 1);
    copia.splice(destino, 0, pieza!);
    onCambio(copia);
  }
  return (
    <div className={estilos.tarjeta}>
      <p className={estilos.rotulo}>Qué es lo más importante para ti (de arriba hacia abajo)</p>
      <ol className={estilos.chips}>
        {orden.map((clave, i) => (
          <li key={clave} className={estilos.chip}>
            <span className={estilos.puesto} aria-hidden="true">
              {i + 1}
            </span>
            <span className={estilos.chipTexto}>{ETIQUETA_PESO[clave]}</span>
            <button
              type="button"
              className={estilos.mover}
              onClick={() => mover(i, -1)}
              disabled={i === 0}
              aria-label={`Subir: ${ETIQUETA_PESO[clave]}`}
            >
              ↑
            </button>
            <button
              type="button"
              className={estilos.mover}
              onClick={() => mover(i, 1)}
              disabled={i === orden.length - 1}
              aria-label={`Bajar: ${ETIQUETA_PESO[clave]}`}
            >
              ↓
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ResumenRestricciones({
  personajes,
  presupuesto,
  orden,
  marcasExcluidas = [],
  soloDisponibles = false,
}: {
  personajes: string[];
  presupuesto: number | null;
  orden: ClavePeso[];
  marcasExcluidas?: string[];
  soloDisponibles?: boolean;
}) {
  return (
    <div className={estilos.tarjeta}>
      <p className={estilos.rotulo}>Esto es lo que vamos a pasar al formulario</p>
      <dl className={estilos.resumen}>
        <dt>Personaje</dt>
        <dd>{personajes.length ? personajes.join(", ") : "Ninguno"}</dd>
        <dt>Tope por hijo</dt>
        <dd>{presupuesto === null ? "Sin tope" : formatearCop(presupuesto)}</dd>
        <dt>Lo más importante</dt>
        <dd>{ETIQUETA_PESO[orden[0] ?? CLAVES_PESO[0]!]}</dd>
        {marcasExcluidas.length > 0 && (
          <>
            <dt>Sin estas marcas</dt>
            <dd>{marcasExcluidas.join(", ")}</dd>
          </>
        )}
        {soloDisponibles && (
          <>
            <dt>Productos</dt>
            <dd>Solo los que hay hoy</dd>
          </>
        )}
      </dl>
    </div>
  );
}

function Producto({ etiqueta, p }: { etiqueta: string; p: TarjetaProducto }) {
  return (
    <div className={estilos.producto}>
      {p.imagen_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className={estilos.fotoChica} src={p.imagen_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
      ) : (
        <span className={estilos.sinFotoChica} aria-hidden="true" />
      )}
      <div>
        <p className={estilos.etiquetaProducto}>{etiqueta}</p>
        <p className={estilos.nombreProducto}>{p.nombre}</p>
        <p className={estilos.precio}>
          {[p.marca, p.precio_unitario !== null ? `${formatearCop(p.precio_unitario)} c/u` : null]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
    </div>
  );
}

function RotuloRenglon({ descripcion, onVer }: { descripcion: string; onVer?: (() => void) | undefined }) {
  return (
    <div className={estilos.rotuloFila}>
      <p className={estilos.rotulo}>{descripcion}</p>
      {onVer && (
        <button type="button" className={estilos.verEnKit} onClick={onVer}>
          Ver en el kit
        </button>
      )}
    </div>
  );
}

export function PropuestaCambio({
  descripcion,
  antes,
  despues,
  unidades,
  delta_cop,
  estado,
  ocupado,
  onAceptar,
  onRechazar,
  onVer,
}: {
  descripcion: string;
  antes: TarjetaProducto;
  despues: TarjetaProducto;
  unidades: number;
  delta_cop: number;
  estado: "pendiente" | "aplicada" | "rechazada";
  ocupado: boolean;
  onAceptar: () => void;
  onRechazar: () => void;
  onVer?: () => void;
}) {
  return (
    <li className={estilos.tarjeta}>
      <RotuloRenglon descripcion={descripcion} onVer={onVer} />
      <div className={estilos.antesDespues}>
        <Producto etiqueta="Ahora" p={antes} />
        <Producto etiqueta="Propuesta" p={despues} />
      </div>
      <p className={delta_cop <= 0 ? estilos.ahorro : estilos.costo}>
        {textoDelta(delta_cop)}
        {unidades > 1 ? ` (${unidades} unidades)` : ""}
      </p>
      {estado === "pendiente" ? (
        <div className={estilos.acciones}>
          <button type="button" className={estilos.primario} onClick={onAceptar} disabled={ocupado}>
            Sí, cambiarlo
          </button>
          <button type="button" className={estilos.secundario} onClick={onRechazar} disabled={ocupado}>
            No, gracias
          </button>
        </div>
      ) : (
        <p className={estilos.ayuda}>{estado === "aplicada" ? "Listo, ya lo cambiamos." : "Lo dejamos como estaba."}</p>
      )}
    </li>
  );
}

export function PropuestaDescarte({
  descripcion,
  motivo_texto,
  producto,
  ahorro_cop,
  aplicable,
  estado,
  ocupado,
  onAceptar,
  onRechazar,
  onVer,
}: {
  descripcion: string;
  motivo_texto: string;
  producto: TarjetaProducto;
  ahorro_cop: number;
  aplicable: boolean;
  estado: "pendiente" | "aplicada" | "rechazada";
  ocupado: boolean;
  onAceptar: () => void;
  onRechazar: () => void;
  onVer?: () => void;
}) {
  return (
    <li className={estilos.tarjeta}>
      <RotuloRenglon descripcion={descripcion} onVer={onVer} />
      <Producto etiqueta="Podrías quitar" p={producto} />
      <p className={estilos.ayuda}>{motivo_texto}</p>
      <p className={estilos.ahorro}>Ahorrarías {formatearCop(ahorro_cop)}</p>
      {!aplicable ? (
        <p className={estilos.aviso}>Por ahora no lo quitamos desde aquí. Si quieres, puedes quitarlo en el renglón de tu kit.</p>
      ) : estado === "pendiente" ? (
        <div className={estilos.acciones}>
          <button type="button" className={estilos.primario} onClick={onAceptar} disabled={ocupado}>
            Sí, quitarlo
          </button>
          <button type="button" className={estilos.secundario} onClick={onRechazar} disabled={ocupado}>
            No, dejarlo
          </button>
        </div>
      ) : (
        <p className={estilos.ayuda}>
          {estado === "aplicada" ? "Listo, lo quitamos. Puedes volver a ponerlo en el renglón del kit." : "Lo dejamos en tu kit."}
        </p>
      )}
    </li>
  );
}

export function ResumenLote({
  texto,
  delta_total_cop,
  propuestas,
  pendientes,
  ocupado,
  onAceptarTodos,
}: {
  texto: string;
  delta_total_cop: number;
  propuestas: number;
  pendientes: number;
  ocupado: boolean;
  onAceptarTodos: () => void;
}) {
  return (
    <li className={estilos.tarjeta}>
      <p className={estilos.nombreProducto}>{texto}</p>
      <p className={delta_total_cop <= 0 ? estilos.ahorro : estilos.costo}>{textoDelta(delta_total_cop)}</p>
      {pendientes > 1 && (
        <div className={estilos.acciones}>
          <button type="button" className={estilos.primario} onClick={onAceptarTodos} disabled={ocupado}>
            Aceptar todos ({pendientes})
          </button>
        </div>
      )}
      {pendientes <= 1 && propuestas > 1 && <p className={estilos.ayuda}>Decide cada cambio de abajo.</p>}
    </li>
  );
}

export function ExplicacionKit({
  perfil,
  renglones,
  por_nivel,
  total_cop,
}: {
  perfil: string;
  renglones: number;
  por_nivel: Record<string, number>;
  total_cop: number | null;
}) {
  const niveles = Object.entries(por_nivel)
    .map(([nivel, n]) => `${n} ${nivel}`)
    .join(", ");
  return (
    <li className={estilos.tarjeta}>
      <p className={estilos.rotulo}>Tu kit {perfil}</p>
      <p className={estilos.nombreProducto}>
        {renglones} renglones{niveles ? `: ${niveles}` : ""}.
      </p>
      {total_cop !== null && <p className={estilos.precio}>Total: {formatearCop(total_cop)}</p>}
    </li>
  );
}
