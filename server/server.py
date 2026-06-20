from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import json

app = FastAPI(title="Servidor de Monitoreo - Torres Completas")

class ConnectionManager:
    """
    Clase para manejar y agrupar las conexiones activas del servidor.
    Mantiene un registro directo de cada torre conectada.
    """
    def __init__(self):
        # Estructura simple: {"torre_1": ws_torre1, "torre_2": ws_torre2}
        self.active_connections: dict[str, WebSocket] = {}

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
            print(f"[DESCONEXIÓN] Torre {torre_id} desconectada.")

manager = ConnectionManager() # Se instancia la clase para manejar conexiones

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