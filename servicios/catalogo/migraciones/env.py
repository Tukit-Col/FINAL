from tukit_catalogo.modelos import Base
from tukit_comun.migraciones import correr

correr("catalogo", Base)
