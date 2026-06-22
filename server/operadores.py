from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

# 1. MODELOS DE DATOS (Dominio)
class Operador(BaseModel):
    id: int
    nombre: str
    email: str
    password_hash: str


class Comando(BaseModel):
    id: Optional[int] = None  # Autogenerado por la BD posteriormente
    id_torre: int
    id_operador: int
    fecha_hora: datetime
    tipo_instruccion: str             # Ej: "REDUCIR_TEMPERATURA", "REDUCIR_CAUDAL"
    estado_ejecucion: str             # Ej: "pendiente", "ejecucion exitosa", "fallo"
    hash_comando: str                 # Hash de integridad/auditoría


class SolicitudComando(BaseModel):
    id_operador: int
    id_torre: int
    tipo_instruccion: str             # Ej: "REDUCIR_TEMPERATURA", "REDUCIR_CAUDAL"


# 2. INTERFAZ DEL REPOSITORIO (El Contrato)
class OperadorRepository(ABC):
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
    def __init__(self):
        # Datos ficticios que simulan las tuplas de la tabla 'operador'
        self._operadores = {
            123: Operador(
                id=123,
                nombre="Diego Rebollo",
                email="diego.rebollo@empresa.com",
                password_hash="pbkdf2:sha256:..."
            ),
            999: Operador(
                id=999,
                nombre="Daniel Támaro",
                email="daniel.tamaro@empresa.com",
                password_hash="pbkdf2:sha256:..."
            )
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
        print(f"[DB MOCK] Comando guardado en tabla 'comando': ID={comando.id}, "
              f"Torre={comando.id_torre}, Operador={comando.id_operador}, Instruccion={comando.tipo_instruccion}")
        return comando
