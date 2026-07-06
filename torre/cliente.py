import asyncio
import json
import os
import random
import ssl
import websockets
import hashlib
import hmac

from Torre import Torre

class Servidor:
	def __init__(self, URL):
		self.URL = URL
		self.conexion = None
		
		self.token = None
		
		with open('/run/secrets/TOKEN-TORRE', 'r') as file:
			self.token = file.read()
		
		return
	
	async def conectar(self):
		if self.conexion != None:
			return
		
		while True:
			try:
				print("Conectando con el servidor central...", flush = True)
				
				contexto_SSL = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
				# Confiar unicamente en el certificado autofirmado del servidor
				contexto_SSL.load_verify_locations('cert.pem')
				# Ignorar discrepancias de hostname en entorno local/docker
				contexto_SSL.check_hostname = False
				
				self.conexion = await websockets.connect(self.URL, ssl = contexto_SSL)
				
				return
			
			except:
				print('Error: No fue posible conectar con el servidor central', flush = True)
			
			await asyncio.sleep(5)
		
		return
	
	async def desconectar(self):
		if self.conexion:
			await self.conexion.close()
			
			self.conexion = None
		
		return
	
	'''
	@param datos: Un diccionario con informacion
	'''
	async def enviar(self, datos):
		await self.conectar()
		
		try:
			payload_para_firmar = dict(datos)
			
			if 'hash_integridad' in payload_para_firmar:
				del payload_para_firmar['hash_integridad']
				
			string_payload = json.dumps(payload_para_firmar, sort_keys=True)
			firma = hmac.new(self.token.encode(), string_payload.encode(), hashlib.sha256).hexdigest()
			
			datos['hash_integridad'] = firma
			
			print(f'Enviando información:', flush = True)
			print(json.dumps(datos, indent = 2), flush = True)
			
			await self.conexion.send(json.dumps(datos))
		
		except:
			print('Error: El servidor no está activo o se perdió la conexión', flush = True)
			
			await self.desconectar()
		
		return
	
	async def recibir(self):
		await self.conectar()
		
		try:
			respuesta = await asyncio.wait_for(self.conexion.recv(), timeout = 1.0)
			paquete = json.loads(respuesta)
			
			hash_recibido = paquete.pop('hash_integridad', None)
			string_payload = json.dumps(paquete, sort_keys=True)
			hash_calculado = hmac.new(self.token.encode(), string_payload.encode(), hashlib.sha256).hexdigest()
			
			if hash_recibido != hash_calculado:
				print("Error de Seguridad: El comando recibido no pasó la prueba de integridad (falsa firma o manipulación)", flush=True)
				return None
			
			return paquete
		
		except asyncio.TimeoutError:
			return None
		
		return

async def main():
	URL_servidor = None
	
	try:
		torre_ID = os.environ['TORRE_ID']
		
		api_key = None
		
		with open('/run/secrets/API-KEY') as file:
			api_key = file.read()
		
		URL_servidor = f"{os.environ['SERVER_BASE_URL']}/torre/{torre_ID}?api_key={api_key}"
	
	except KeyError:
		print('Error: Faltan variables de entorno requeridas (TORRE_ID, SERVER_BASE_URL)', flush = True)
		return
	except Exception as e:
		print(f'Error: No fue posible construir la URL de comunicación con el servidor: {e}', flush = True)
		
		return
	
	torre = Torre(torre_ID = torre_ID)
	servidor = Servidor(URL = URL_servidor)
	
	while True:
		torre.actualizar()
		
		lecturas = torre.obtener_lecturas()
		
		await servidor.enviar(lecturas)
		
		respuesta = await servidor.recibir()
		
		torre.aplicar_operacion(respuesta)
		
		await asyncio.sleep(random.uniform(3.0, 5.0))

if __name__ == '__main__':
	try:
		asyncio.run(main())
	
	except KeyboardInterrupt:
		print()
		print('=== SIMULACION DE TORRE TERMINADA ===')