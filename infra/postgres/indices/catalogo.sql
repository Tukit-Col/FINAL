-- Indices de la busqueda hibrida de Catalogo.
--
-- Por que en un archivo SQL y no en `__table_args__` del modelo: `create_all`
-- crea los indices que el modelo declara, pero HNSW y las clases de operadores
-- de trigramas son sintaxis exclusiva de Postgres. Declararlos arriba romperia
-- `create_all` contra SQLite, que es donde corren las pruebas de dominio del
-- servicio, y se perderia la propiedad que sostiene toda la capa de acceso: el
-- mismo modelo corriendo en la prueba y en el motor real. Separarlos tambien
-- deja el ajuste fisico donde se ajusta (aqui, junto al init) y no mezclado con
-- las reglas de negocio del modelo.
--
-- Lo aplica `make bd-indices` sobre `tukit_catalogo`, por la convencion de que
-- cada archivo de este directorio se llama como el servicio dueno de su base.
-- Todo es `IF NOT EXISTS` para que repetir la meta no cueste nada.

-- Canal semantico. Coseno porque el emparejamiento compara direccion de
-- significado y no magnitud: "cuaderno cosido 100 hojas" y "cuaderno cosido
-- grande 100 hojas Norma" describen lo mismo con largos distintos y deben
-- quedar cerca. La clase de operadores tiene que coincidir con el operador que
-- use la consulta (`<=>`); si no coinciden el planificador ignora el indice en
-- silencio y el recorrido vuelve a ser secuencial sobre toda la tabla.
CREATE INDEX IF NOT EXISTS ix_producto_embedding_hnsw
    ON producto_canonico USING hnsw (embedding vector_cosine_ops);

-- Canal lexico. Resuelve lo que el semantico no ve: referencias con codigo,
-- marcas mal escritas en la lista del colegio, abreviaturas. Sin el GIN de
-- trigramas, `similarity(nombre, ...)` obliga a calcular la similitud fila por
-- fila; con el, el filtro por `%` se resuelve desde el indice.
--
-- Depende de la extension pg_trgm: la habilita el init de Postgres en volumenes
-- nuevos y `tukit_comun.bd.MotorServicio.asegurar_extensiones` en los que ya
-- existian. Si faltara, esta sentencia falla aqui y no en una consulta remota.
CREATE INDEX IF NOT EXISTS ix_producto_nombre_trgm
    ON producto_canonico USING gin (nombre gin_trgm_ops);
