from tukit_comun.migraciones import correr
from tukit_operacion.modelos import Base

correr("operacion", Base)
