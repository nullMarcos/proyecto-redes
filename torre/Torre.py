import random

from enum import Enum

'''
TODO:

Hasta el momento, los sensores no están actuando como sensores como tal, pues es desde esa clase que también se modifican los valores.

Para hacerlo bien, habría que crear una clase `Variable` que se encargue de mantener el estado. Luego las clases `Sensor` y una nueva clase `Actuador` 
leen y escriben ahí, pero para hacer eso habría que implementar mutex, porque en teoría las modificaciones se debiesen poder de forma simultánea 
a las lecturas.
'''

class Sensor:
	class Estado(Enum):
		NORMAL = 'NORMAL'
		ANOMALO = 'ANOMALO'
	
	'''
	@param valor Valor inicial del sensor
	@param unidad Unidad de medida
	@param limites Una tupla con dos valores, los limites de operacion de la variable
	@param ruido Una tupla con dos valores, indican el intervalo de oscilacion del ruido en las lecturas normales
	@param anomalia Una tupla con dos valores, indican el intervalo de oscilacion de las lecturas anomalas
	'''
	def __init__(self, valor, unidad, limites, ruido, anomalia):
		self.valor = valor
		self.unidad = unidad
		self.limites = limites
		
		self.ruido = ruido
		self.anomalia = anomalia
		
		self.estado = self.Estado.NORMAL
		
		return
	
	def modificar(self, diferencia):
		self.valor += diferencia
		
		self.valor = max(self.valor, self.limites[0])
		self.valor = min(self.valor, self.limites[1])
		
		self.estado = 'NORMAL'
		
		return
	
	def actualizar(self):
		self.cambiar_estado()
		
		if self.estado == self.Estado.NORMAL:
			self.valor += random.uniform(self.ruido[0], self.ruido[1])
		
		if self.estado == self.Estado.ANOMALO:
			self.valor += random.uniform(self.anomalia[0], self.anomalia[1])
		
		return
	
	def obtener_lectura(self):
		lectura = {
			'valor': round(self.valor, 2),
			'unidad': self.unidad
		}
		
		return lectura
	
	def cambiar_estado(self):
		if random.random() < 0.10:
			match self.estado:
				case self.Estado.NORMAL:
					self.estado = self.Estado.ANOMALO
				
				case self.Estado.ANOMALO:
					self.estado = self.Estado.NORMAL
		
		return


class Torre:
	def __init__(self, torre_ID):
		self.torre_ID = torre_ID
		
		self.sensores = {
			'ph': Sensor(valor = 4.0, unidad = 'pH', limites = [0, 1000], ruido = [-2, 2], anomalia = [10, 20]),
			'nivel': Sensor(valor = 40.0, unidad = '%', limites = [0, 1000], ruido = [-2, 2], anomalia = [10, 20]),
			'presion': Sensor(valor = 125.0, unidad = 'kPa', limites = [0, 1000], ruido = [-2, 2], anomalia = [10, 20]),
			'temperatura': Sensor(valor = 80.0, unidad = '°C', limites = [0, 1000], ruido = [-2, 2], anomalia = [10, 20]),
			'flujo_clo2': Sensor(valor = 5.0, unidad = 'L/s', limites = [0, 1000], ruido = [-2, 2], anomalia = [10, 20]),
			'flujo_pulpa': Sensor(valor = 15.0, unidad = 'L/s', limites = [0, 1000], ruido = [-2, 2], anomalia = [10, 20]),
		}
	
	def obtener_lecturas(self):
		datos = {
			'torre_ID': self.torre_ID,
			'lecturas': {},
		}
		
		for sensor in self.sensores.keys():
			datos['lecturas'][sensor] = self.sensores[sensor].obtener_lectura()
		
		datos['lecturas']['caudal'] = {
			'valor': round(self.sensores['flujo_clo2'].valor + self.sensores['flujo_pulpa'].valor, 2),
			'unidad': 'L/s',
		}
		
		return datos
	
	'''
	@param operacion Un diccionario que indica el nombre de la operacion y los parametros necesarios
	'''
	def aplicar_operacion(self, operacion):
		if operacion == None:
			return
		
		match operacion.get('nombre', ''):
			case 'AUMENTAR_FLUJO_PULPA':
				self.sensores['flujo_pulpa'].modificar(operacion.get(diferencia, 0))
			
			case 'DISMINUIR_FLUJO_PULPA':
				self.sensores['flujo_pulpa'].modificar(operacion.get(diferencia, 0))
			
			case 'AUMENTAR_FLUJO_CLO2':
				self.sensores['flujo_clo2'].modificar(operacion.get(diferencia, 0))
			
			case 'DISMINUIR_FLUJO_CLO2':
				self.sensores['flujo_clo2'].modificar(operacion.get(diferencia, 0))
			
			case 'AUMENTAR_TEMPERATURA':
				self.sensores['temperatura'].modificar(operacion.get(diferencia, 0))
			
			case 'DISMINUIR_TEMPERATURA':
				self.sensores['temperatura'].modificar(operacion.get(diferencia, 0))
		
		return
	
	def actualizar(self):
		for sensor in self.sensores.keys():
			self.sensores[sensor].actualizar()
		
		return