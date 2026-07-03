import asyncio
import json
import os
import random
import ssl
import websockets
import hashlib

from Torre import Torre

'''
TODO:
- Revisar pertinencia de SSL:
	* https://docs.python.org/3/library/ssl.html#module-ssl
	* https://docs.python.org/3/library/ssl.html#ssl-security

- Crear clase para manejar conexion con el servidor. Así como está ahora hay muchas cosas que pueden salir mal.
- Probablemente sería mejor que el envío de datos y la recepción de instrucciones operen en hilos diferentes.
'''

class Servidor:
	def __init__(self, URL):
		self.URL = URL
		self.conexion = None
		
		return
	
	async def conectar(self):
		if self.conexion != None:
			return
		
		while True:
			try:
				print("Conectando con el servidor central...", flush = True)
				
				contexto_SSL = ssl.create_default_context()
				contexto_SSL.check_hostname = False
				contexto_SSL.verify_mode = ssl.CERT_NONE
				
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
	@param datos Un diccionario con informacion
	'''
	async def enviar(self, datos):
		await self.conectar()
		
		try:
			token = os.environ.get('TOKEN_SECRETO', '')
			payload_para_firmar = dict(datos)
			if 'hash_integridad' in payload_para_firmar:
				del payload_para_firmar['hash_integridad']
				
			string_payload = json.dumps(payload_para_firmar, sort_keys=True)
			firma = hashlib.sha256((string_payload + token).encode()).hexdigest()
			
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
			
			return json.loads(respuesta)
		
		except asyncio.TimeoutError:
			return None
		
		return

async def main():
	URL_servidor = None
	
	try:
		torre_ID = os.environ['TORRE_ID']
		URL_servidor = f'{os.environ['SERVER_BASE_URL']}/torre/{torre_ID}'
	
	except:
		print('Error: No fue posible construir la URL de comunicacion con el servidor', flush = True)
		
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