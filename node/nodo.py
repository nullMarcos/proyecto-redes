import asyncio
import random
import argparse
import os
import json
import ssl
import websockets

"""
@class TorreBlanqueamiento
@brief Simula el comportamiento de un nodo (torre de blanqueamiento de celulosa) en un entorno industrial.
       Genera datos de sensores, simula anomalías y se comunica con un servidor central vía WebSockets seguros (wss).
"""
class TorreBlanqueamiento:

    """
    Constructor de la clase TorreBlanqueamiento.
    Inicializa la identidad de la torre, la URL del servidor y el estado base de los sensores.
    
    @param torre_id Identificador único numérico para la torre.
    """
    def __init__(self, torre_id):
        self.torre_id = torre_id
        # Construimos la URL agregando el ID de la torre al final
        base_url = os.environ.get("SERVER_URL", "wss://localhost:5050/ws/torre/")
        self.url_servidor = f"{base_url}{self.torre_id}"
        self.ws = None
        
        self.estado_sensores = {
            "temperatura": {"valor_base": 80.0, "estado": "NORMAL"},
            "flujo_pulpa": {"valor_base": 15.0, "estado": "NORMAL"},
            "flujo_clo2" : {"valor_base": 5.0, "estado": "NORMAL"}
        }

    """
    Envía los datos de los sensores al servidor mediante una petición HTTP POST.
    Si el servidor no está disponible, utiliza una simulación (Mock) para generar una respuesta.
    
    @param datos_torre Diccionario que contiene el paquete de datos generados por los sensores.
    @return Un diccionario con la respuesta del servidor o del mock generalmente con una "instruccion".
    """
    async def enviar_datos_servidor(self, datos_torre):

        #Intento de conectarse con el servidor vía WebSockets seguros (WSS)
        try:
            # Reutilizamos la conexión si ya está activa, si no, conectamos
            if self.ws is None:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                self.ws = await websockets.connect(self.url_servidor, ssl=ssl_context)
            
            # Enviamos el paquete
            await self.ws.send(json.dumps(datos_torre))
            
            # Esperamos respuesta del servidor con un tiempo límite (timeout)
            try:
                respuesta_str = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                return json.loads(respuesta_str)
            except asyncio.TimeoutError:
                # Si el servidor no envía nada, seguimos sin instrucción
                return {"instruccion": "N/A"}

        except Exception as e:
            # print(f"Error al enviar datos al servidor: {e}")
            print(f"[Torre {self.torre_id}] El servidor no está activo o se perdió la conexión, continuando ejecucion con un MOCK")
            
            # Cerramos la conexión corrupta para que el próximo ciclo intente reconectar
            if self.ws:
                await self.ws.close()
                self.ws = None
            
            #MOCK
            respuesta_mock = {"instruccion": "N/A"}
            temperatura = datos_torre["sensores"]["temperatura"]["valor"]
            caudal = datos_torre["sensores"]["caudal"]["valor"]

            if temperatura > 150.0:
                respuesta_mock["instruccion"] = "REDUCIR_TEMPERATURA"
            elif caudal > 50.0:
                respuesta_mock["instruccion"] = "REDUCIR_CAUDAL"

            return respuesta_mock

    """
    Calcula y actualiza el valor actual de un sensor en base a su estado (NORMAL o ANOMALO).
    
    @param sensor Nombre del sensor (ej. "temperatura", "flujo_pulpa").
    @param ruido_min Valor mínimo de fluctuación aleatoria en estado NORMAL.
    @param ruido_max Valor máximo de fluctuación aleatoria en estado NORMAL.
    @param anomalia_min Valor mínimo de incremento en estado ANOMALO.
    @param anomalia_max Valor máximo de incremento en estado ANOMALO.
    @return El valor actual calculado para el sensor.
    """
    def actualizar_valores(self, sensor, ruido_min, ruido_max, anomalia_min, anomalia_max):
        if self.estado_sensores[sensor]["estado"] == "NORMAL":
            return self.estado_sensores[sensor]["valor_base"] + random.uniform(ruido_min, ruido_max)
        else: #ANOMALO
            self.estado_sensores[sensor]["valor_base"] += random.uniform(anomalia_min, anomalia_max)
            return self.estado_sensores[sensor]["valor_base"]
    
    """
    Actúa como el mecanismo de control de la torre. Modifica los parámetros
    físicos (variables base) en función de las órdenes recibidas del servidor.
    
    @param instruccion Cadena de texto con la orden proveniente del servidor.
    """
    def aplicar_instrucciones(self, instruccion):

        #Actuadores basados en la instruccion del servidor
        if instruccion != "N/A":
            print(f"Instruccion del servidor para torre {self.torre_id}: {instruccion}")

        #Se reducen la temperatura o los flujos de pulpa y clo2 a sus valores base normales

        if instruccion == "REDUCIR_TEMPERATURA":
            self.estado_sensores["temperatura"]["valor_base"] = 80.0
            self.estado_sensores["temperatura"]["estado"] = "NORMAL"

        elif instruccion == "REDUCIR_CAUDAL":
            self.estado_sensores["flujo_pulpa"]["valor_base"] = 15.0
            self.estado_sensores["flujo_clo2"]["valor_base"] = 5.0
            self.estado_sensores["flujo_pulpa"]["estado"] = "NORMAL"
            self.estado_sensores["flujo_clo2"]["estado"] = "NORMAL" 

    """
    Método principal (Bucle Infinito) que arranca la simulación de la torre.
    Genera el comportamiento, empaqueta los datos, los transmite y ejecuta las instrucciones dadas por un servidor central.
    """
    async def iniciar_simulacion(self):

        print("Simulacion de torre de blanqueamiento: ")

        while True:

            #Si el sensor se encuentra en estado NORMAL, hay una probabilidad del 10% de que adquiera un comportamiento anomalo
            for sensor in self.estado_sensores.keys():

                if self.estado_sensores[sensor]["estado"] == "NORMAL" and random.random() < 0.10:
                    self.estado_sensores[sensor]["estado"] = "ANOMALO"
                    print(f"[Torre {self.torre_id}] Sensor de {sensor} ha adquirido un comportamiento anomalo.")

            temperatura = self.actualizar_valores("temperatura", -2.0, 2.0, 10.0, 20.0)
            flujo_pulpa = self.actualizar_valores("flujo_pulpa", -2.0, 2.0, 5.0, 10.0)
            flujo_clo2  = self.actualizar_valores("flujo_clo2", -2.0, 2.0, 3.0, 6.0)

            #Empaquetamiento de datos
            datos_torre = {
                "torre_id": self.torre_id,
                "sensores": {
                    "nivel"      : {"valor": round(random.uniform(40.0, 80.0), 2), "unidad": "%"},
                    "caudal"     : {"valor": round(flujo_pulpa + flujo_clo2, 2), "unidad": "L/s"},
                    "temperatura": {"valor": round(temperatura, 2), "unidad": "°C"},
                    "ph"         : {"valor": round(random.uniform(3.5, 4.5), 2), "unidad": "pH"},
                    "presion"    : {"valor": round(random.uniform(100.0, 200.0), 2), "unidad": "kPa"}
                }
            }

            print(f"[Torre {self.torre_id}] Transmitiendo:")
            print(f"{datos_torre['sensores']['nivel']['valor']} {datos_torre['sensores']['nivel']['unidad']}")
            print(f"{datos_torre['sensores']['caudal']['valor']} {datos_torre['sensores']['caudal']['unidad']}")
            print(f"{datos_torre['sensores']['temperatura']['valor']} {datos_torre['sensores']['temperatura']['unidad']}")
            print(f"{datos_torre['sensores']['ph']['valor']} {datos_torre['sensores']['ph']['unidad']}")
            print(f"{datos_torre['sensores']['presion']['valor']} {datos_torre['sensores']['presion']['unidad']}")
            print()

            #Envio de datos y recepcion de instrucciones
            respuesta_servidor = await self.enviar_datos_servidor(datos_torre)
            instruccion = respuesta_servidor.get("instruccion", "N/A")

            self.aplicar_instrucciones(instruccion)

            await asyncio.sleep(random.uniform(3.0, 5.0))

#BLOQUE DE EJECUCION PRINCIPAL
async def main():
    parser = argparse.ArgumentParser(description="Simulador de datos de torre de blanqueamiento.")
    parser.add_argument("--n_torres", required=True, help="Numero de torres a simular (ej: 5)")
    args = parser.parse_args()
    
    #Guardamos las tareas asíncronas para esta ejecucion
    n_torres = int(args.n_torres)
    tareas = []

    for i in range(1, n_torres + 1):
        
        #Instancia de una torre de blanqueamiento
        torre = TorreBlanqueamiento(torre_id=i)

        #Creamos una tarea asíncrona para cada torre
        tarea = asyncio.create_task(torre.iniciar_simulacion())
        tareas.append(tarea)

        #Pausa asíncrona para evitar que todas las torres inicien exactamente al mismo tiempo
        await asyncio.sleep(1)

    print("Todas las torres iniciadas. Presiona Ctrl+C para detener la simulacion.")

    try:
        await asyncio.gather(*tareas)
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulacion terminada")