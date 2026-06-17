from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import json

app = FastAPI(title="Servidor de Monitoreo - Nodos Independientes")

class ConnectionManager:
    """Clase para manejar y agrupar las conexiones activas de servidor.
        Organiza los sensores individualmente en base al ID de su respectiva torre.
    """
    def __init__(self):
        # Estructura: {"torre_1": {"sensor_temp": ws1, "sensor_ph": ws2}, "torre_2": {...}}
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, torre_id: str, tipo_sensor: str):
        """Función para aceptar y registrar las conecciones entrantes de los sensores.

        :param websocket: El objeto de conexión (canal) abierto con el sensor.
        :type websocket: WebSocket
        :param torre_id: Identificador de a qué torre pertenece el sensor
        :type torre_id: str
        :param tipo_sensor: Variable que especifica qué tipo de sensor es (sensor_temp, sensor_ph, etc.)
        :type tipo_sensor: str
        """        
        await websocket.accept()
        
        # Si es la primera vez que escuchamos de esta torre, le creamos su espacio
        if torre_id not in self.active_connections:
            self.active_connections[torre_id] = {}
            
        # Registramos el sensor específico dentro de su torre
        self.active_connections[torre_id][tipo_sensor] = websocket
        print(f"[CONEXIÓN] {tipo_sensor} de la {torre_id} conectado.")

    def disconnect(self, torre_id: str, tipo_sensor: str):
        """Elimina el registro de un sensor cuando se desconecta del servidor.

        :param torre_id: Identificador de la torre a la cual pertenece el sensor a desconectar
        :type torre_id: str
        :param tipo_sensor: Variable que especifica qué tipo de sensor es (sensor_temp, sensor_ph, etc.)
        :type tipo_sensor: str
        """        
        # Eliminamos solo el sensor que se cayó, no toda la torre
        if torre_id in self.active_connections and tipo_sensor in self.active_connections[torre_id]:
            del self.active_connections[torre_id][tipo_sensor]
            print(f"[DESCONEXIÓN] {tipo_sensor} de la {torre_id} desconectado.")

manager = ConnectionManager() #Se instancia la clase para manejar conexiones

# Variables para armar telemetría de torre antes de guardarse en la base de datos
estado_torres = {}

@app.websocket("/ws/torre/{torre_id}/sensor/{tipo_sensor}")
async def manejar_sensor(websocket: WebSocket, torre_id: str, tipo_sensor: str):
    """Maneja la conexión de un sensor individual perteneciente a una torre.

    :param websocket: El objeto de conexión (canal) abierto con el sensor.
    :type websocket: WebSocket
    :param torre_id: Identificador de a qué torre pertenece el sensor
    :type torre_id: str
    :param tipo_sensor: Variable que especifica qué tipo de sensor es (sensor_temp, sensor_ph, etc.)
    :type tipo_sensor: str
    """    
    await manager.connect(websocket, torre_id, tipo_sensor) #Se llama al connection manager
    
    # Inicializamos el estado en memoria de la torre si no existe
    if torre_id not in estado_torres:
        estado_torres[torre_id] = {
            "temperatura": None, "ph": None, "presion": None, 
            "nivel": None, "caudal_entrada": None, "caudal_salida": None
        }
    
    try:
        while True:
            data = await websocket.receive_text()
            paquete = json.loads(data)
            
            # Validar Token e Integridad (Hash) 
            
            # Actualizar solo el valor que corresponde a este sensor en la memoria
            valor = paquete.get("valor")
            estado_torres[torre_id][tipo_sensor] = valor
            
            print(f"[ACTUALIZACIÓN] {torre_id} - {tipo_sensor}: {valor}")
            print(f"Estado actual de {torre_id}: {estado_torres[torre_id]}")
            
            #Lógica para guardar en Base de Datos:

    except WebSocketDisconnect:
        manager.disconnect(torre_id, tipo_sensor)
    except json.JSONDecodeError:
        print(f"[ERROR] Paquete inválido de {tipo_sensor} en {torre_id}")

def start():
    """Función para iniciar el servidor HTTP y WebSocket
    """    
    print("Iniciando servidor FastAPI...")
    uvicorn.run(app, host="0.0.0.0", port=5050) #Escucha activa

if __name__ == "__main__":
    start()