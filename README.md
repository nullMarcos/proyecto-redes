# Monitoreo Industrial de Torres de Blanqueamiento

**Integrantes** 

- Gabriel Castillo
- Marcos Martínez
- Daniel Támaro
- Jesús Guevara
- Diego Rebollo

Este proyecto implementa un sistema de monitoreo y control en tiempo real para torres de blanqueamiento industrial. Consta de dos componentes principales que se comunican de forma segura mediante WebSockets sobre TLS/SSL (WSS) con verificación de integridad de paquetes:

1. **Servidor Central (`servidor`)**: Expone una API HTTP/WebSocket implementada en FastAPI para recibir telemetría, analizar anomalías en tiempo real (fugas, desviaciones químicas, sobrepresión), gatillar comandos de mitigación automáticos y registrar auditorías.
2. **Torre Simuladora (`torre`)**: Un cliente WebSocket que sirve como interfaz de control para los sensores de la torre (pH, presión, temperatura, flujo, etc.) y los actuadores. Además, ejecuta los comandos recibidos desde el servidor.

---

## Requisitos Previos

* **Docker** y **Docker Compose** (para la ejecución en contenedores).
* **Python 3.14+** 

---

## Configuración de Secretos

El sistema utiliza secretos montados para la autenticación y la validación de integridad. Debes configurar los siguientes archivos antes de iniciar el proyecto.

### 1. Directorio `torre/secrets/`
Crea los siguientes archivos en la ruta `torre/secrets/`:

* **`API-KEY`**: Clave utilizada para autenticar la conexión WebSocket inicial.
  * **Contenido:** Solicitar a los autores del proyecto. 
  * **Importante:** Debe coincidir con el hash de clave API registrado en la base de datos para la torre correspondiente (la torre 1 viene preconfigurada con esta clave en el sembrado de desarrollo).

* **`TOKEN-TORRE`**: Token secreto para generar y verificar firmas HMAC-SHA256 del lado de la torre.
  * **Contenido:** Solicitar a los autores del proyecto. 
  * **Importante:** Asegúrate de que **no contenga espacios ni saltos de línea al final**. Si se edita manualmente, es aconsejable verificar que coincida carácter por carácter con el secreto del servidor.

### 2. Directorio `servidor/secrets/`
Crea el siguiente archivo en la ruta `servidor/secrets/`:

* **`TOKEN-SERVIDOR`**: Token secreto para verificar y firmar las transmisiones HMAC-SHA256 del lado del servidor.
  * **Contenido:** Debe ser **idéntico** a `TOKEN-TORRE` para que las pruebas de integridad de los paquetes no fallen.

---

## Ejecución del Proyecto Mediante Docker Compose

Docker Compose levantará ambos servicios en contenedores aislados y configurará automáticamente la red interna, los volúmenes para la base de datos SQLite y los secretos.

1. Asegúrate de estar en el directorio raíz del proyecto.
2. Construye y levanta los contenedores:
   ```bash
   docker compose up --build
   ```
3. El servidor iniciará en `https://localhost:5050` y el cliente de la torre se conectará automáticamente.

---

## Seguridad e Integridad de Datos

* **Cifrado en tránsito (TLS/SSL):** Toda la comunicación HTTP y WebSocket se realiza bajo HTTPS/WSS utilizando certificados autofirmados ubicados en `servidor/certs/`.
* **Autenticación de Nodos:** La torre debe presentar su `API-KEY` en los parámetros de la URL de conexión. Si la clave no es válida o no está registrada, la conexión WebSocket se rechaza inmediatamente con el código `1008`.
* **Auditoría de Integridad (HMAC):** Para evitar la inyección o manipulación de telemetría y comandos en tránsito, cada payload enviado se firma usando HMAC-SHA256 con el token compartido (`TOKEN-TORRE` / `TOKEN-SERVIDOR`). Si un paquete recibido no coincide con el hash calculado, se rechaza y se registra una alerta de seguridad en la base de datos.
