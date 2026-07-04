from datetime import datetime
from typing import Optional, List
from sqlalchemy import ForeignKey, String, Float, DateTime, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.database import Base

class TorreBlanqueamiento(Base):
    __tablename__ = "torre_blanqueamiento"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    estado: Mapped[str] = mapped_column(String(50), default="OFFLINE")
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relaciones
    reportes: Mapped[List["ReporteTelemetria"]] = relationship(back_populates="torre")
    comandos: Mapped[List["Comando"]] = relationship(back_populates="torre")


class Operador(Base):
    __tablename__ = "operador"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relaciones
    comandos: Mapped[List["Comando"]] = relationship(back_populates="operador")


class ReporteTelemetria(Base):
    __tablename__ = "reporte_telemetria"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_torre: Mapped[int] = mapped_column(ForeignKey("torre_blanqueamiento.id"), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    nivel: Mapped[Optional[float]] = mapped_column(Float)
    flujo_pulpa: Mapped[Optional[float]] = mapped_column(Float)
    flujo_clo2: Mapped[Optional[float]] = mapped_column(Float)
    caudal_total: Mapped[Optional[float]] = mapped_column(Float)
    temperatura: Mapped[Optional[float]] = mapped_column(Float)
    ph: Mapped[Optional[float]] = mapped_column(Float)
    presion: Mapped[Optional[float]] = mapped_column(Float)

    # Relaciones
    torre: Mapped["TorreBlanqueamiento"] = relationship(back_populates="reportes")

    # Índices
    __table_args__ = (
        Index("idx_torre_fecha", "id_torre", "fecha_hora"),
    )


class Comando(Base):
    __tablename__ = "comando"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_torre: Mapped[int] = mapped_column(ForeignKey("torre_blanqueamiento.id"), nullable=False)
    id_operador: Mapped[int] = mapped_column(ForeignKey("operador.id"), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tipo_instruccion: Mapped[str] = mapped_column(String(100))
    valor_parametro: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estado_ejecucion: Mapped[str] = mapped_column(String(50))
    hash_comando: Mapped[str] = mapped_column(String(255))

    # Relaciones
    torre: Mapped["TorreBlanqueamiento"] = relationship(back_populates="comandos")
    operador: Mapped["Operador"] = relationship(back_populates="comandos")


class AlertaProceso(Base):
    __tablename__ = "alerta_proceso"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_torre: Mapped[int] = mapped_column(ForeignKey("torre_blanqueamiento.id"), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tipo_alerta: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)


class AlertaSeguridad(Base):
    __tablename__ = "alerta_seguridad"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_torre: Mapped[int] = mapped_column(ForeignKey("torre_blanqueamiento.id"), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tipo_evento: Mapped[str] = mapped_column(String(100))
    origen_ip: Mapped[Optional[str]] = mapped_column(String(45))
    payload_sospechoso: Mapped[Optional[str]] = mapped_column(Text)