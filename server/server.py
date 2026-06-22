from typing import Optional
from datetime import datetime
import hashlib
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
import uvicorn
import json

from operadores import InMemoryOperadorRepository, OperadorRepository, Comando, SolicitudComando

app = FastAPI(title="Servidor de Monitoreo - Torres Completas")
operador_repo: OperadorRepository = InMemoryOperadorRepository() 

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

    def disconnect(self, torre_id: str):
        """
        Elimina el registro de una torre cuando se desconecta.

        :param torre_id: Identificador de la torre a desconectar.
        :type torre_id: str
        """        
        if torre_id in self.active_connections:
            del self.active_connections[torre_id]
        if torre_id in self.pending_instructions:
            del self.pending_instructions[torre_id]
        print(f"[DESCONEXIÓN] Torre {torre_id} desconectada.")
    
    def add_instruction(self, torre_id: int, comando: Comando):
        """Guarda una instrucción para ser enviada en la próxima telemetría."""
        self.pending_instructions[torre_id] = comando
    
    def consume_instruction(self, torre_id: int) -> Optional[Comando]:
        return self.pending_instructions.pop(torre_id, None)


manager = ConnectionManager() # Se instancia la clase para manejar conexiones

# Endpoint HTTP: Para que el Operador envíe comandos
@app.post("/api/control/comando")
async def send_operator_command(solicitud: SolicitudComando):
    # 1. Validar operador
    operador = operador_repo.obtener_por_id(solicitud.id_operador)
    if not operador: 
        raise HTTPException(status_code=404, detail="Operador no registrado.")
    
    # 2. Validar que la torre esté activa
    if str(solicitud.id_torre) not in manager.active_connections:
        raise HTTPException(status_code=400, detail=f"La torre {solicitud.id_torre} no está conectada.")
    
    # 3. Generar hash del comando para la auditoría
    fecha_actual = datetime.now()
    seed_hash = f"{solicitud.id_operador}-{solicitud.id_torre}-{solicitud.tipo_instruccion}-{fecha_actual.isoformat()}"
    hash_val = hashlib.sha256(seed_hash.encode()).hexdigest()
    
    # 4. Crear objeto de entidad Comando
    nuevo_comando = Comando(
        id_torre=solicitud.id_torre,
        id_operador=solicitud.id_operador,
        fecha_hora=fecha_actual,
        tipo_instruccion=solicitud.tipo_instruccion,
        estado_ejecucion="pendiente",
        hash_comando=hash_val
    )
    
    # 5. Registrar en el repositorio
    comando_registrado = operador_repo.registrar_comando(nuevo_comando)
    
    # 6. Encolar la instrucción para la torre
    manager.add_instruction(solicitud.id_torre, comando_registrado)
    
    return {
        "status": "success",
        "id_comando": comando_registrado.id,
        "hash_comando": comando_registrado.hash_comando,
        "message": f"Instrucción '{solicitud.tipo_instruccion}' registrada y lista para ejecución."
    }

@app.websocket("/ws/torre/{torre_id}")
async def manejar_torre(websocket: WebSocket, torre_id: str):
    """
    Maneja la conexión en tiempo real con un nodo (Torre completa).

    :param websocket: El objeto de conexión (canal) abierto con la torre.
    :type websocket: WebSocket
    :param torre_id: Identificador único de la torre.
    :type torre_id: str
    """    
    await manager.connect(websocket, torre_id)
    
    try:
        while True:
            # Recibimos el paquete completo de la torre
            data = await websocket.receive_text()
            paquete = json.loads(data)
            
            print(f"[TELEMETRÍA RECIBIDA - {torre_id}] {paquete}")
        
            # Extraer el hash del paquete y validar integridad.
            # Validar token_autenticacion contra la BD.
            # Guardar todo el paquete directamente en la tabla reporte_telemetria.
            # Evaluar si los valores superan umbrales (ej. presión muy alta) 
            # --- RESPUESTA DE INSTRUCCIONES AL NODO ---
            try:
                torre_int = int(torre_id)
                comando_pendiente = manager.consume_instruction(torre_int)
            except ValueError:
                comando_pendiente = None
                
            if comando_pendiente:
                instruccion = comando_pendiente.tipo_instruccion
                comando_pendiente.estado_ejecucion = "ejecucion exitosa"
                print(f"[COMANDO ENVIADO] Comando ID {comando_pendiente.id} enviado a torre {torre_id}: {instruccion}")
            else:
                instruccion = "N/A"
            
            # Responder inmediatamente con la instrucción
            await websocket.send_text(json.dumps({"instruccion": instruccion}))

    except WebSocketDisconnect:
        manager.disconnect(torre_id)
    except json.JSONDecodeError:
        print(f"[ERROR] Paquete inválido recibido de la Torre {torre_id}")
    except Exception as e:
        print(f"[ERROR CRÍTICO] {torre_id}: {e}")
        manager.disconnect(torre_id)

def start():
    """Función para iniciar el servidor HTTP y WebSocket."""    
    print("Iniciando servidor FastAPI con HTTPS...")
    #Se inicia el servidor con certificados para HTTPS
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=5050, 
        ssl_keyfile="server/certs/key.pem", 
        ssl_certfile="server/certs/cert.pem"
    )

if __name__ == "__main__":
    start()