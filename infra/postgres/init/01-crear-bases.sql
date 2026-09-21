-- Crea las cinco bases del sistema y habilita pgvector en cada una.
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

-- pgvector se habilita por base: la extension no es global. Catalogo la usa hoy
-- (embeddings de producto, Vector(1024)); inteligencia la usara al portar la
-- resolucion semantica. Se habilita en las cinco para no tener que recordar
-- hacerlo despues, cuesta nada en las que no la usan.
\connect tukit_identidad
CREATE EXTENSION IF NOT EXISTS vector;

\connect tukit_catalogo
CREATE EXTENSION IF NOT EXISTS vector;

\connect tukit_inteligencia
CREATE EXTENSION IF NOT EXISTS vector;

\connect tukit_comercio
CREATE EXTENSION IF NOT EXISTS vector;

\connect tukit_operacion
CREATE EXTENSION IF NOT EXISTS vector;
