from tukit_comercio.modelos import Base
from tukit_comun.migraciones import correr

correr("comercio", Base)
