import {
  NotebookPen,
  Pencil,
  Palette,
  Paperclip,
  Ruler,
  Package,
  type LucideIcon,
} from "lucide-react";
import { personajesPorHijo, type LineaKit } from "@tukit/contrato";
import {
  categoriaDeLinea,
  notaSinEncaje,
  personajeLegible,
  type CategoriaKit,
} from "@/lib/kit-vista";
import styles from "./Kits.module.css";

export const ICONO_CATEGORIA: Record<CategoriaKit, LucideIcon> = {
  cuadernos: NotebookPen,
  escritura: Pencil,
  arte: Palette,
  papeleria: Paperclip,
  geometria: Ruler,
  otros: Package,
};

type FilaSinEncaje = { hijo: string; concepto: string; personaje: string };

export default function FranjaFan({
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

const MAX_MINIATURAS = 10;

export function MiniaturasHijo({ lineas }: { lineas: LineaKit[] }) {
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

export function TarjetasFan({ lineas, veces }: { lineas: LineaKit[]; veces?: Record<string, number> }) {
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
