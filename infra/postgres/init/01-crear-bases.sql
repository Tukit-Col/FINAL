-- Crea las cinco bases del sistema y habilita sus extensiones en cada una.
--
-- Corre una sola vez, cuando el volumen de datos esta vacio (lo ejecuta el
-- entrypoint de la imagen de Postgres). Son las cinco bases que declara el
-- manifiesto: identidad, catalogo, inteligencia, comercio y operacion. Los
-- servicios sin base propia (ingesta, gateway) no aparecen aqui a proposito.
--
-- Una base, un dueno. El aislamiento de dominio no se afloja por compartir
-- motor: cada servicio se conecta solo a la suya, y la funcion de aptitud
-- `test_ningun_servicio_nombra_la_base_de_otro` lo verifica en cada integracion.

CREATE DATABASE tukit_identidad;
CREATE DATABASE tukit_catalogo;
CREATE DATABASE tukit_inteligencia;
CREATE DATABASE tukit_comercio;
CREATE DATABASE tukit_operacion;

-- Las extensiones se habilitan por base: no son globales. Catalogo usa las dos
-- hoy, inteligencia las usara al portar la resolucion semantica. Se habilitan
-- en las cinco para no tener que recordar hacerlo despues, cuesta nada en las
-- que no las usan.
--
-- `vector`: canal semantico. Los embeddings de producto son Vector(1024), y
-- sin la extension el tipo no existe: el esquema de catalogo ni siquiera
-- materializa.
--
-- `pg_trgm`: canal lexico. El emparejamiento es busqueda HIBRIDA, y el canal
-- lexico es el que resuelve lo que el semantico no: nombres con codigo de
-- referencia, marcas mal escritas, abreviaturas de la lista del colegio. Da la
-- similitud por trigramas (`%`, `similarity()`) y la clase de operadores
-- `gin_trgm_ops` que hace viable el indice sobre el nombre del producto.
--
-- Este archivo corre UNA sola vez, con el volumen vacio. Quien ya tenga el
-- volumen creado no lo vera nunca, asi que la habilitacion se repite de forma
-- idempotente en `tukit_comun.bd.MotorServicio.asegurar_extensiones`, que corre
-- en cada `make bd-esquema`. Aqui queda porque es donde se espera encontrarlo.
\connect tukit_identidad
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

\connect tukit_catalogo
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

\connect tukit_inteligencia
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

\connect tukit_comercio
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

\connect tukit_operacion
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
