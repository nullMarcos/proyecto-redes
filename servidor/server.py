"""Servidor de monitoreo para torres completas"""

from typing import Optional
from types import SimpleNamespace
from datetime import datetime
import hashlib
import json
import os
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy.orm import Session

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import models
from database.database import engine, SessionLocal, get_db
from database.repositories import (
    SQLOperadorRepository,
    SQLTorreRepository,
    SQLTelemetriaRepository,
    SQLAlertaRepository,
    SQLComandoRepository,
)
from operadores import Comando, SolicitudComando

app = FastAPI(title="Servidor de Monitoreo - Torres Completas")

# models.Base.metadata.create_all(bind=engine)

class ConnectionManager:
    """
    Clase para manejar y agrupar las conexiones activas del servidor.
    Mantiene un registro directo de cada torre conectada.
    """

    def __init__(self):
        # Estructura simple: {"torre_1": ws_torre1, "torre_2": ws_torre2}
        self.active_connections: dict[str, WebSocket] = {}

        # Guardamos instrucciones pendientes por torre
        self.pending_instructions: dict[str, list[Comando]] = {}

    async def connect(self, websocket: WebSocket, torre_id: str):
        """
        Acepta y registra la conexión entrante de una torre.

        :param websocket: El objeto de conexión (canal) abierto con la torre.
        :type websocket: WebSocket
        :param torre_id: Identificador de la torre que se conecta.
        :type torre_id: str
        """
        await websocket.accept()

        # Registramos la torre
        self.active_connections[torre_id] = websocket
        print(f"[CONEXIÓN] Torre {torre_id} conectada al servidor.")

    def disconnect(self, torre_id: int):
        """
        Elimina el registro de una torre cuando se desconecta.

        :param torre_id: Identificador de la torre a desconectar.
        :type torre_id: int
        """
        if torre_id in self.active_connections:
            del self.active_connections[torre_id]
        if torre_id in self.pending_instructions:
            del self.pending_instructions[torre_id]
        print(f"[DESCONEXIÓN] Torre {torre_id} desconectada.")

    def add_instruction(self, torre_id: int, comando: Comando):
        """Encola una instrucción para que no se pierda si entran varias en paralelo."""
        if torre_id not in self.pending_instructions:
            self.pending_instructions[torre_id] = []
        self.pending_instructions[torre_id].append(comando)

    def consume_instruction(self, torre_id: int) -> Optional[Comando]:
        """Devuelve la siguiente instrucción pendiente de la cola FIFO y lo elimina de la lista."""
        if (
            torre_id in self.pending_instructions
            and self.pending_instructions[torre_id]
        ):
            return self.pending_instructions[torre_id].pop(0)
        return None


manager = ConnectionManager()  # Se instancia la clase para manejar conexiones


# Endpoint HTTP: Para que el Operador envíe comandos
@app.post("/api/control/comando")
async def send_operator_command(solicitud: SolicitudComando, db: Session = Depends(get_db)):
    """
    Endpoint para que un operador envíe un comando a una torre específica.
    param solicitud: Objeto que contiene los detalles del comando a enviar.
    type solicitud: SolicitudComando
    return: Diccionario con el estado de la operación y detalles del comando registrado.
    rtype: dict
    """

    repo = SQLOperadorRepository(db)
    # 1. Validar operador
    operador = repo.obtener_por_id(solicitud.id_operador)
    if not operador:
        raise HTTPException(status_code=404, detail="Operador no registrado.")

    # 2. Validar que la torre esté activa
    if str(solicitud.id_torre) not in manager.active_connections:
        raise HTTPException(
            status_code=400, detail=f"La torre {solicitud.id_torre} no está conectada."
        )

    # 3. Generar hash del comando para la auditoría
    fecha_actual = datetime.now()
    seed_hash = (
        f"{solicitud.id_operador}-{solicitud.id_torre}-"
        f"{solicitud.tipo_instruccion}-{fecha_actual.isoformat()}"
    )
    hash_val = hashlib.sha256(seed_hash.encode()).hexdigest()

    # 4. Crear objeto de entidad Comando
    nuevo_comando = Comando(
        id_torre=solicitud.id_torre,
        id_operador=solicitud.id_operador,
        fecha_hora=fecha_actual,
        tipo_instruccion=solicitud.tipo_instruccion,
        valor_parametro=solicitud.valor_parametro,
        estado_ejecucion="pendiente",
        hash_comando=hash_val,
    )

    # 5. Registrar en el repositorio
    comando_registrado = repo.registrar_comando(nuevo_comando)

    # 6. Encolar la instrucción para la torre
    manager.add_instruction(solicitud.id_torre, comando_registrado)

    return {
        "status": "success",
        "id_comando": comando_registrado.id,
        "hash_comando": comando_registrado.hash_comando,
        "message": f"Instrucción '{solicitud.tipo_instruccion}' registrada y lista para ejecución.",
    }


@app.get("/")
async def inicio():
    return {"message": "Servidor central"}


@app.websocket("/ws/torre/{torre_id}")
async def manejar_torre(websocket: WebSocket, torre_id: str):
    """
    Maneja la conexión en tiempo real con un nodo (Torre completa).

    :param websocket: El objeto de conexión (canal) abierto con la torre.
    :type websocket: WebSocket
    :param torre_id: Identificador único de la torre.
    :type torre_id: str
    """
    try:
        torre_int = int(torre_id)
    except ValueError:
        torre_int = None

    await manager.connect(websocket, torre_id)

    if torre_int is not None:
        # Registrar estado de conexión ONLINE en base de datos
        with SessionLocal() as db:
            torre_repo = SQLTorreRepository(db)
            try:
                torre_repo.actualizar_estado(torre_int, "ONLINE")
            except Exception as e:
                print(f"[ERROR ESTADO TORRE] No se pudo cambiar a ONLINE: {e}")

    try:
        while True:
            # Recibimos el paquete completo de la torre
            data = await websocket.receive_text()
            paquete = json.loads(data)

            # === AUDITORÍA DE INTEGRIDAD ===
            hash_recibido = paquete.pop('hash_integridad', None)
            token = os.environ.get('TOKEN_SECRETO', '')
            string_payload = json.dumps(paquete, sort_keys=True)
            hash_calculado = hashlib.sha256((string_payload + token).encode()).hexdigest()
            
            if hash_recibido != hash_calculado:
                print(f"[ALERTA DE SEGURIDAD] Paquete de Torre {torre_id} rechazado por fallo de integridad.")
                # Registrar alerta de seguridad en BD
                if torre_int is not None:
                    with SessionLocal() as db:
                        alerta_repo = SQLAlertaRepository(db)
                        try:
                            alerta_repo.registrar_alerta_seguridad(
                                id_torre=torre_int,
                                tipo_evento="FALLO_INTEGRIDAD",
                                origen_ip=websocket.client.host if websocket.client else None,
                                payload=string_payload
                            )
                        except Exception as e:
                            print(f"[ERROR REGISTRO ALERTA SEGURIDAD] {e}")
                continue # Ignora el paquete malicioso
            # ===============================

            print(f"[TELEMETRÍA RECIBIDA - {torre_id}] {paquete}")
    
            with SessionLocal() as db: 
                repo = SQLOperadorRepository(db)
                telemetria_repo = SQLTelemetriaRepository(db)
                alerta_repo = SQLAlertaRepository(db)
                try:
                    lecturas = paquete.get("lecturas", {})

                    # Extracción segura de los valores simulados
                    ph = lecturas.get("ph", {}).get("valor", 4.0)
                    presion = lecturas.get("presion", {}).get("valor", 125.0)
                    temperatura = lecturas.get("temperatura", {}).get("valor", 80.0)
                    flujo_pulpa = lecturas.get("flujo_pulpa", {}).get("valor", 15.0)
                    flujo_clo2 = lecturas.get("flujo_clo2", {}).get("valor", 5.0)
                    caudal = lecturas.get("caudal", {}).get("valor", 0.0)
                    nivel = lecturas.get("nivel", {}).get("valor", 40.0)

                    # Guardar telemetría a través del repositorio
                    reporte_dominio = SimpleNamespace(
                        id_torre=torre_int,
                        ph=ph,
                        presion=presion,
                        nivel=nivel,
                        temperatura=temperatura,
                        flujo_clo2=flujo_clo2,
                        flujo_pulpa=flujo_pulpa,
                        caudal_total=caudal,
                        fecha_hora=datetime.now()
                    )
                    telemetria_repo.guardar_reporte(reporte_dominio)

                    # Algoritmo de Detección de Fugas cruzando Caudal y Presión
                    if caudal >= 15.0 and presion < ((caudal * 7.75) * 0.85):
                        print(
                            f"[ALERTA DE FUGA - TORRE {torre_id}] Caudal alto ({caudal} L/s) "
                            f"pero presión anormalmente baja ({presion} kPa). Posible ruptura en la línea."
                        )

                        alerta_repo.registrar_alerta_proceso(
                            id_torre=torre_int,
                            tipo="POSIBLE_FUGA",
                            desc=f"Caudal alto ({caudal} L/s) pero presión baja ({presion} kPa)."
                        )

                    # Alerta por desviación de neutralización química (pH fuera de rango crítico)
                    if ph < 2.5 or ph > 8.5:
                        print(
                            f"[ALERTA - TORRE {torre_id}] Anomalía química detectada. pH crítico: {ph}"
                        )

                        alerta_repo.registrar_alerta_proceso(
                            id_torre=torre_int,
                            tipo="ANOMALIA_QUIMICA",
                            desc=f"pH fuera de rango crítico: {ph}"
                        )

                    # Alerta por desviación térmica severa
                    if temperatura > 95.0:
                        print(
                            f"[ALERTA - TORRE {torre_id}] Temperatura fuera de umbral seguro: {temperatura}°C"
                        )

                        alerta_repo.registrar_alerta_proceso(
                            id_torre=torre_int,
                            tipo="ANOMALIA_TEMPERATURA",
                            desc=f"Temperatura fuera de rango crítico: {temperatura}"
                        )

                    # Control Automatizado: Mitigación inmediata por sobrepresión física
                    if presion > 150.0:
                        print(
                            f"[CONTROL AUTOMÁTICO - TORRE {torre_id}] ¡Presión crítica! ({presion} kPa). "
                            f"Gatillando apertura de válvula de alivio de emergencia."
                        )

                        # Generamos el comando de mitigación de manera automática
                        comando_emergencia = Comando(
                            id_torre=torre_int,
                            id_operador=0,  # ID 0 representará las acciones automáticas del Sistema Central
                            fecha_hora=datetime.now(),
                            tipo_instruccion="ACTIVAR_VALVULA_ALIVIO",
                            valor_parametro=1.0,  # Parámetro o señal de activación
                            estado_ejecucion="pendiente",
                            hash_comando="SISTEMA_AUTO_MITIGATION_SHA256",
                        )
                        # Encolamos la instrucción de emergencia para que sea consumida de inmediato
                        comando_registrado = repo.registrar_comando(comando_emergencia)
                        manager.add_instruction(torre_int, comando_registrado)
                    
                    # Guardamos todos los cambios hechos en esta iteración (alertas y comandos automáticos)
                    db.commit()

                except Exception as err_analisis:
                    db.rollback()
                    print(
                        f"[ERROR ANÁLISIS DE TELEMETRÍA] No se pudieron evaluar las métricas: {err_analisis}"
                    )

            try:
                comando_pendiente = manager.consume_instruction(torre_int)
            except ValueError:
                comando_pendiente = None

            if comando_pendiente:
                instruccion = comando_pendiente.tipo_instruccion
                valor_parametro = comando_pendiente.valor_parametro
                comando_pendiente.estado_ejecucion = "ejecucion exitosa"
                # Actualizar estado del comando en base de datos
                with SessionLocal() as db:
                    cmd_repo = SQLComandoRepository(db)
                    try:
                        cmd_repo.actualizar_estado(comando_pendiente.id, "ejecucion exitosa")
                    except Exception as e:
                        print(f"[ERROR ACTUALIZACIÓN COMANDO] {e}")

                print(
                    f"[COMANDO ENVIADO] Comando ID {comando_pendiente.id} "
                    f"enviado a torre {torre_id}: "
                    f"{instruccion} con valor {valor_parametro}"
                )

                respuesta_payload = {
                    "operacion": {
                        "nombre": instruccion,
                        "diferencia": valor_parametro,
                    },
                }

            else:
                respuesta_payload = {"instruccion": "N/A", "valor_parametro": None}

            # Responder inmediatamente con la instrucción (ya sea N/A, del operador o automática)
            await websocket.send_text(json.dumps(respuesta_payload))

    except WebSocketDisconnect:
        manager.disconnect(torre_id)
        if torre_int is not None:
            with SessionLocal() as db:
                torre_repo = SQLTorreRepository(db)
                try:
                    torre_repo.actualizar_estado(torre_int, "OFFLINE")
                except Exception as e:
                    print(f"[ERROR ESTADO TORRE] No se pudo cambiar a OFFLINE: {e}")

    except json.JSONDecodeError:
        print(f"[ERROR] Paquete inválido recibido de la Torre {torre_id}")

    except Exception as e:
        print(f"[ERROR CRÍTICO] {torre_id}: {e}")
        manager.disconnect(torre_id)
        if torre_int is not None:
            with SessionLocal() as db:
                torre_repo = SQLTorreRepository(db)
                try:
                    torre_repo.actualizar_estado(torre_int, "OFFLINE")
                except Exception as e:
                    print(f"[ERROR ESTADO TORRE] No se pudo cambiar a OFFLINE: {e}")


def start():
    """Función para iniciar el servidor HTTP y WebSocket."""
    print("Iniciando servidor FastAPI con HTTPS...")

    # Se inicia el servidor con certificados para HTTPS
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5050,
        ssl_keyfile=str(BASE_DIR / "certs" / "key.pem"),
        ssl_certfile=str(BASE_DIR / "certs" / "cert.pem"),

    )


if __name__ == "__main__":
    start()
