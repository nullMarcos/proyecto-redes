"""Módulo de operadores y comandos"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, model_validator


class TipoInstruccion(str, Enum):
	"""Enum que representa los tipos de instrucciones
	que un operador puede enviar a la torre de control."""
	
	AUMENTAR_FLUJO_PULPA = "AUMENTAR_FLUJO_PULPA"
	DISMINUIR_FLUJO_PULPA = "DISMINUIR_FLUJO_PULPA"
	AUMENTAR_FLUJO_CLO2 = "AUMENTAR_FLUJO_CLO2"
	DISMINUIR_FLUJO_CLO2 = "DISMINUIR_FLUJO_CLO2"
	AUMENTAR_TEMPERATURA = "AUMENTAR_TEMPERATURA"
	DISMINUIR_TEMPERATURA = "DISMINUIR_TEMPERATURA"
	ACTIVAR_VALVULA_ALIVIO = "ACTIVAR_VALVULA_ALIVIO"


# 1. MODELOS DE DATOS (Dominio)
class Operador(BaseModel):
	"""Representa un operador que puede enviar comandos a la torre de control."""
	
	id: int
	nombre: str
	email: str
	password_hash: str


class Comando(BaseModel):
	"""Representa un comando enviado por un operador a la torre de control."""
	
	id: Optional[int] = None  # Autogenerado por la BD posteriormente
	id_torre: int
	id_operador: int
	fecha_hora: datetime
	tipo_instruccion: TipoInstruccion
	valor_parametro: Optional[float] = None
	estado_ejecucion: str  # Ej: "pendiente", "ejecucion exitosa", "fallo"
	hash_comando: str  # Hash de integridad/auditoría


class SolicitudComando(BaseModel):
	"""Representa la solicitud de un comando que un operador envía a la torre de control."""
	
	id_operador: int
	id_torre: int
	tipo_instruccion: TipoInstruccion
	valor_parametro: Optional[float] = None
	
	@model_validator(mode="after")
	def verificador_parametro_segun_instruccion(self):
		"""Valida que si la instrucción requiere un valor numérico, este no sea None."""
		# Si la instrucción requiere un valor numérico y viene vacío, lanzamos error
		instrucciones_con_valor = {
			TipoInstruccion.AUMENTAR_TEMPERATURA,
			TipoInstruccion.DISMINUIR_TEMPERATURA,
			TipoInstruccion.AUMENTAR_FLUJO_PULPA,
			TipoInstruccion.DISMINUIR_FLUJO_PULPA,
		}
		
		if (
			self.tipo_instruccion in instrucciones_con_valor
			and self.valor_parametro is None
		):
			raise ValueError(
				f"La instrucción {self.tipo_instruccion} requiere especificar un 'valor_parametro'."
			)
		
		return self


# 2. INTERFAZ DEL REPOSITORIO (El Contrato)
class OperadorRepository(ABC):
	"""Interfaz que define los métodos que cualquier
	implementación de repositorio de operadores debe cumplir."""
	
	@abstractmethod
	def obtener_por_id(self, id_operador: int) -> Optional[Operador]:
		"""Busca un operador por su ID único en la base de datos."""
		pass
	
	@abstractmethod
	def registrar_comando(self, comando: Comando) -> Comando:
		"""Registra la ejecución de un comando en la base de datos."""
		pass


# 3. IMPLEMENTACIÓN EN MEMORIA (Mock temporal)
class InMemoryOperadorRepository(OperadorRepository):
	"""Implementación en memoria del repositorio de operadores y comandos."""
	
	def __init__(self):
		# Datos ficticios que simulan las tuplas de la tabla 'operador'
		self._operadores = {
			123: Operador(
				id=123,
				nombre="Diego Rebollo",
				email="diego.rebollo@empresa.com",
				password_hash="pbkdf2:sha256:...",
			),
			999: Operador(
				id=999,
				nombre="Daniel Támaro",
				email="daniel.tamaro@empresa.com",
				password_hash="pbkdf2:sha256:...",
			),
		}
		# Lista temporal para simular la tabla 'comando'
		self.comandos_registrados = []
		self._next_comando_id = 1
	
	def obtener_por_id(self, id_operador: int) -> Optional[Operador]:
		return self._operadores.get(id_operador)
	
	def registrar_comando(self, comando: Comando) -> Comando:
		# Simulamos la autogeneración de ID por la BD
		comando.id = self._next_comando_id
		self._next_comando_id += 1
		
		self.comandos_registrados.append(comando)
		print(
			f"[DB MOCK] Comando guardado en tabla 'comando': ID={comando.id}, "
			f"Torre={comando.id_torre}, "
			f"Operador={comando.id_operador}, "
			f"Instruccion={comando.tipo_instruccion}"
		)
		return comando