// `/catalogo` — la SPA de administración del catálogo (P4c).
//
// Reemplaza al antiguo gestor de huecos: en vez de listar solo los conceptos
// sin cubrir, es un gestor completo de `producto_canonico` — búsqueda con
// filtros, CRUD de todos los campos, gestión de imagen por URL, re-etiqueta
// (nivel/personaje/marca/atributos) y re-clasificación (mover de concepto).
//
// Server Component: hace las tres LECTURAS iniciales directo contra el origen
// (sin salto HTTP) —la primera página de productos, la lista de conceptos para
// filtrar/reclasificar y los personajes para el autocompletado— y las pasa al
// cliente. Toda escritura y toda búsqueda interactiva posterior van por los
// Route Handlers de `/api/catalogo/**`.

import { origenDeDatos } from "@tukit/contrato/servidor";
import GestorCatalogo from "@/components/GestorCatalogo";
import type { OpcionConcepto } from "@/components/PanelReclasificar";
import styles from "./Catalogo.module.css";

export const dynamic = "force-dynamic";

export default async function PaginaCatalogo() {
  const origen = origenDeDatos();

  // Las tres lecturas en paralelo: primera página, conceptos y personajes.
  const [paginaInicial, catalogo, personajes] = await Promise.all([
    origen.buscarProductos({ por_pagina: 24, pagina: 1 }),
    origen.catalogo(),
    origen.personajes(),
  ]);

  const conceptos: OpcionConcepto[] = catalogo.conceptos
    .map((c) => ({ codigo: c.codigo, nombre: c.nombre_canonico }))
    .sort((a, b) => a.nombre.localeCompare(b.nombre));

  const nombresPersonajes = personajes.map((p) => p.nombre);

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Catálogo · productos</h1>
          <p className={styles.bajada}>
            El gestor del catálogo canónico. Buscá un producto, editá todos sus campos,
            re-etiquetalo (nivel, personaje, marca), cambialo de concepto o dalo de baja. Lo que
            cambies aquí vale para todos los trabajos, no para uno.
          </p>
        </div>
        <dl className={styles.resumen}>
          <div>
            <dt>Productos</dt>
            <dd className="cifra">{catalogo.resumen.productos}</dd>
          </div>
          <div>
            <dt>Con foto</dt>
            <dd className="cifra">{catalogo.resumen.productos_con_foto}</dd>
          </div>
          <div>
            <dt>Sin revisar</dt>
            <dd className="cifra">{catalogo.resumen.productos_sin_revisar}</dd>
          </div>
        </dl>
      </header>

      <GestorCatalogo
        paginaInicial={paginaInicial}
        conceptos={conceptos}
        personajes={nombresPersonajes}
      />
    </div>
  );
}
