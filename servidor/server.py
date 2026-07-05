"""Servidor de monitoreo para torres completas"""

from typing import Optional
from types import SimpleNamespace
from datetime import datetime, timedelta
import hashlib
import json
import os
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from werkzeug.security import check_password_hash
from sqlalchemy.orm import Session

import hmac

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

# Configuración JWT
SECRET_KEY = os.environ.get("JWT_SECRET", "super_secreto_jwt_para_desarrollo")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_operador(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    repo = SQLOperadorRepository(db)
    operador = repo.obtener_por_email(email=email)
    if operador is None:
        raise credentials_exception
    return operador

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    repo = SQLOperadorRepository(db)
    operador = repo.obtener_por_email(form_data.username)
    if not operador or not check_password_hash(operador.password_hash, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": operador.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.on_event("startup")
def inicializar_base_de_datos():
    """Inicializa la base de datos con datos de prueba (seeding) si está vacía."""
    print("[INIT DB] Comprobando inicialización de datos de prueba...")
    with SessionLocal() as db:
        # Crear el operador de prueba (ID 123) si no existe
        operador_existente = db.query(models.Operador).filter_by(id=123).first()
        if not operador_existente:
            nuevo_operador = models.Operador(
                id=123,
                nombre="Diego Rebollo",
                email="diego.rebollo@salmoftware.com",
                password_hash="pbkdf2:sha256:600000$mock$5e04cb667108b8d7f02b7b6fdf29a6f97f3beba38af537d15a56fb5687c7843a2d"
            )
            db.add(nuevo_operador)
            print("[INIT DB] Operador por defecto creado (ID: 123).")
        
        # Crear el operador de sistema (ID 0) si no existe
        operador_sistema = db.query(models.Operador).filter_by(id=0).first()
        if not operador_sistema:
            nuevo_operador_sistema = models.Operador(
                id=0,
                nombre="Sistema Central (Automático)",
                email="sistema.central@salmoftware.com",
                password_hash="pbkdf2:sha256:600000$system$default_password_hash"
            )
            db.add(nuevo_operador_sistema)
            print("[INIT DB] Operador Sistema Central creado (ID: 0).")
        
        # Crear la torre por defecto (ID 1) si no existe
        torre_existente = db.query(models.TorreBlanqueamiento).filter_by(id=1).first()
        if not torre_existente:
            # Clave de desarrollo: "mi_super_secreto_key_123"
            dev_key = "mi_super_secreto_key_123"
            dev_key_hash = hashlib.sha256(dev_key.encode()).hexdigest()
            
            nueva_torre = models.TorreBlanqueamiento(
                id=1,
                sector="Sector Norte - Desarrollo",
                estado="OFFLINE",
                api_key_hash=dev_key_hash
            )
            db.add(nueva_torre)
            print("[INIT DB] Torre por defecto creada (ID: 1, API Key: 'mi_super_secreto_key_123').")
        
        db.commit()

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
async def send_operator_command(
    solicitud: SolicitudComando, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_operador)
):
    """
    Endpoint para que un operador envíe un comando a una torre específica.
    param solicitud: Objeto que contiene los detalles del comando a enviar.
    type solicitud: SolicitudComando
    return: Diccionario con el estado de la operación y detalles del comando registrado.
    rtype: dict
    """

    repo = SQLOperadorRepository(db)
    
    # 1. Validar operador (Ya autenticado por JWT)
    # Sobrescribimos el ID del operador en la solicitud con el del usuario real logueado
    solicitud.id_operador = current_user.id

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
async def manejar_torre(websocket: WebSocket, torre_id: str, api_key: Optional[str] = None):
    """
    Maneja la conexión en tiempo real con un nodo (Torre completa).

    :param websocket: El objeto de conexión (canal) abierto con la torre.
    :type websocket: WebSocket
    :param torre_id: Identificador único de la torre.
    :type torre_id: str
    :param api_key: Clave API opcional para autenticación del nodo.
    :type api_key: Optional[str]
    """
    try:
        torre_int = int(torre_id)
    except ValueError:
        torre_int = None

    # Si el ID es inválido, rechazar conexión
    if torre_int is None:
        await websocket.accept()
        await websocket.close(code=1008)
        print(f"[CONEXIÓN RECHAZADA] ID de torre inválido: '{torre_id}'")
        return

    # Validar presencia de la API Key
    if not api_key:
        await websocket.accept()
        await websocket.close(code=1008)
        print(f"[CONEXIÓN RECHAZADA] Torre {torre_id} intentó conectar sin API Key.")
        return

    # Autenticar la API Key contra la base de datos
    authenticated = False
    with SessionLocal() as db:
        torre_repo = SQLTorreRepository(db)
        alerta_repo = SQLAlertaRepository(db)
        torre = torre_repo.obtener_por_id(torre_int)
        
        if not torre:
            print(f"[CONEXIÓN RECHAZADA] La torre {torre_id} no está registrada en la base de datos.")
        else:
            import hmac
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            if hmac.compare_digest(key_hash, torre.api_key_hash):
                authenticated = True
            else:
                print(f"[ALERTA DE SEGURIDAD] Intento de conexión con API Key inválida para torre {torre_id}.")
                try:
                    alerta_repo.registrar_alerta_seguridad(
                        id_torre=torre_int,
                        tipo_evento="CONEXION_API_KEY_INVALIDA",
                        origen_ip=websocket.client.host if websocket.client else None,
                        payload=f"API Key incorrecta provista: {api_key[:3]}..." if api_key else ""
                    )
                except Exception as e:
                    print(f"[ERROR REGISTRO ALERTA SEGURIDAD] {e}")

    if not authenticated:
        await websocket.accept()
        await websocket.close(code=1008)
        return

    # Si está autenticado, procedemos a conectar y registrar
    await manager.connect(websocket, torre_id)

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
            hash_calculado = hmac.new(token.encode(), string_payload.encode(), hashlib.sha256).hexdigest()
            
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

                        # Control Automático: Cierre de válvulas ante posible fuga para evitar derrames
                        hash_val_fuga = hashlib.sha256(f"0-{torre_int}-AUTO-FUGA-{datetime.now().isoformat()}".encode()).hexdigest()
                        cmd_fuga1 = Comando(
                            id_torre=torre_int, id_operador=0, fecha_hora=datetime.now(),
                            tipo_instruccion="DISMINUIR_FLUJO_PULPA", valor_parametro=100.0,
                            estado_ejecucion="pendiente", hash_comando=hash_val_fuga
                        )
                        cmd_fuga2 = Comando(
                            id_torre=torre_int, id_operador=0, fecha_hora=datetime.now(),
                            tipo_instruccion="DISMINUIR_FLUJO_CLO2", valor_parametro=50.0,
                            estado_ejecucion="pendiente", hash_comando=hash_val_fuga
                        )
                        manager.add_instruction(torre_int, repo.registrar_comando(cmd_fuga1))
                        manager.add_instruction(torre_int, repo.registrar_comando(cmd_fuga2))

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

                        # Control Automático: Mitigación para estabilizar pH
                        hash_val_ph = hashlib.sha256(f"0-{torre_int}-AUTO-PH-{datetime.now().isoformat()}".encode()).hexdigest()
                        if ph < 2.5:
                            # Diluir acidez aumentando flujo de pulpa
                            cmd_ph = Comando(
                                id_torre=torre_int, id_operador=0, fecha_hora=datetime.now(),
                                tipo_instruccion="AUMENTAR_FLUJO_PULPA", valor_parametro=5.0,
                                estado_ejecucion="pendiente", hash_comando=hash_val_ph
                            )
                        else:
                            # Acidificar la mezcla aumentando flujo de CLO2
                            cmd_ph = Comando(
                                id_torre=torre_int, id_operador=0, fecha_hora=datetime.now(),
                                tipo_instruccion="AUMENTAR_FLUJO_CLO2", valor_parametro=2.0,
                                estado_ejecucion="pendiente", hash_comando=hash_val_ph
                            )
                        manager.add_instruction(torre_int, repo.registrar_comando(cmd_ph))

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

                        # Control Automático: Mitigación por temperatura excesiva
                        hash_val_temp = hashlib.sha256(f"0-{torre_int}-AUTO-TEMP-{datetime.now().isoformat()}".encode()).hexdigest()
                        cmd_temp = Comando(
                            id_torre=torre_int, id_operador=0, fecha_hora=datetime.now(),
                            tipo_instruccion="DISMINUIR_TEMPERATURA", valor_parametro=10.0,
                            estado_ejecucion="pendiente", hash_comando=hash_val_temp
                        )
                        manager.add_instruction(torre_int, repo.registrar_comando(cmd_temp))

                    # Control Automatizado: Mitigación inmediata por sobrepresión física
                    if presion > 150.0:
                        print(
                            f"[CONTROL AUTOMÁTICO - TORRE {torre_id}] ¡Presión crítica! ({presion} kPa). "
                            f"Gatillando apertura de válvula de alivio de emergencia."
                        )

                        # Registrar formalmente la Alerta de Proceso en la BD antes de mitigar
                        alerta_repo.registrar_alerta_proceso(
                            id_torre=torre_int,
                            tipo="SOBREPRESION_CRITICA",
                            desc=f"Presión superó los 150 kPa ({presion} kPa). Se ha gatillado la válvula de alivio."
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

            # Firmar el payload
            token = os.environ.get('TOKEN_SECRETO', '')
            string_payload_resp = json.dumps(respuesta_payload, sort_keys=True)
            firma = hmac.new(token.encode(), string_payload_resp.encode(), hashlib.sha256).hexdigest()
            respuesta_payload['hash_integridad'] = firma

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
