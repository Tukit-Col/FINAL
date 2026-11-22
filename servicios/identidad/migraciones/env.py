from tukit_comun.migraciones import correr
from tukit_identidad.modelos import Base

correr("identidad", Base)
