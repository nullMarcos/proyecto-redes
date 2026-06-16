import socket
import threading

PORT = 5050
SERVER = socket.gethostbyname(socket.gethostname()) #Se obtiene ip de la máquina actual

ADDR = (SERVER, PORT) #Dirección del servidor

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #Se utiliza SOCK_STREAM para protocolo tcp
server.bind(ADDR)

#Función para manejar la comunicación con un nodo
def manejar_nodo(conn, addr):
    """Función para manejar los clientes (sensores)

    :param conn: parámetro que guarda la información del paquete
    :type conn: socket
    :param addr: parámetro que guarda la IP del cliente
    :type addr: string
    """    
    

    print(f"[NUEVA CONECCIÓN] {addr} conectado.")
    connected = True
    while connected:
        #¿Cómo discrimar entre sensores?
        pass
        


def start():
    """Función para iniciar el servidor 
    """    
    server.listen()
    while True:
        conn, addr = server.accept()
        #Se utilizan hilos para manejar los nodos
        thread = threading.Thread(target = manejar_nodo, args=(conn, addr)) 
        thread.start()
        print(f"[CONECCIONES ACTIVAS] {threading.activeCount() -1}")


print("Iniciando servidor")
start()