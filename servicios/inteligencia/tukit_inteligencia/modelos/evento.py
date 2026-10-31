"""Los eventos que Inteligencia ya proceso, por origen e id (ADR 0046).

Con RabbitMQ la entrega es al menos una vez: un mensaje vuelve a llegar si el
broker no vio la confirmacion, o si el publicador lo publico otra vez porque
perdio el commit de su bandeja. Un `lista_verificada` repetido crearia otro
trabajo y otro kit para el mismo padre, asi que el sondeador de listas anota
aqui cada evento que procesa, y la marca entra en la misma transaccion que crea
el trabajo.

La forma es la que espera `tukit_comun.consumidor.RegistroEnTabla`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EventoProcesado(Base):
    """Un evento de otro servicio que este ya proceso."""

    __tablename__ = "evento_procesado"

    # El servicio que lo emitio: el id solo es unico dentro de su bandeja.
    origen: Mapped[str] = mapped_column(String(32), primary_key=True)
    evento_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    procesado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
