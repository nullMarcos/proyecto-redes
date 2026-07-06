import random
from enum import Enum


class Sensor:
	class Estado(Enum):
		NORMAL = "NORMAL"
		ANOMALO = "ANOMALO"
	
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
		
		# Mantener el valor estrictamente dentro de los límites físicos
		self.valor = max(self.valor, self.limites[0])
		self.valor = min(self.valor, self.limites[1])
		
		# CORREGIDO: Mantener el tipo Enum correcto
		self.estado = self.Estado.NORMAL
		
		return
	
	def actualizar(self):
		self.cambiar_estado()
		
		if self.estado == self.Estado.NORMAL:
			self.valor += random.uniform(self.ruido[0], self.ruido[1])
		
		if self.estado == self.Estado.ANOMALO:
			self.valor += random.uniform(self.anomalia[0], self.anomalia[1])
		
		# Forzar límites también en las fluctuaciones automáticas
		self.valor = max(self.valor, self.limites[0])
		self.valor = min(self.valor, self.limites[1])
		
		return
	
	def obtener_lectura(self):
		lectura = {
			"valor": round(self.valor, 2),
			"unidad": self.unidad
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

		# AJUSTADO: Rangos y límites realistas para la simulación industrial
		self.sensores = {
			"ph": Sensor(valor = 4.0, unidad = "pH", limites = [0, 14], ruido = [-0.1, 0.1], anomalia = [0.5, 1.5]),
			"nivel": Sensor(valor = 40.0, unidad = "%", limites = [0, 100], ruido = [-0.5, 0.5], anomalia = [2.0, 5.0]),
			"presion": Sensor(valor = 155.0,unidad = "kPa",limites = [0, 1000],ruido = [-2.0, 2.0],anomalia = [10.0, 20.0]),
			"temperatura": Sensor(valor = 80.0, unidad = "°C", limites = [0, 150], ruido = [-0.5, 0.5], anomalia = [3.0, 6.0]),
			"flujo_clo2": Sensor(valor = 5.0, unidad = "L/s", limites = [0, 50], ruido = [-0.2, 0.2], anomalia = [1.0, 2.5]),
			"flujo_pulpa": Sensor(valor = 15.0, unidad = "L/s", limites = [0, 100], ruido = [-0.2, 0.2], anomalia = [1.0, 3.0]),
		}
		
		return
	
	def obtener_lecturas(self):
		datos = {
			"torre_ID": self.torre_ID,
			"lecturas": {},
		}
		
		for sensor in self.sensores.keys():
			datos["lecturas"][sensor] = self.sensores[sensor].obtener_lectura()
		
		datos["lecturas"]["caudal"] = {
			"valor": round(self.sensores["flujo_clo2"].valor + self.sensores["flujo_pulpa"].valor, 2),
			"unidad": "L/s",
		}
		
		return datos
	
	def aplicar_operacion(self, respuesta_servidor):
		if not respuesta_servidor or "operacion" not in respuesta_servidor:
			return
		
		# Desempaquetar el objeto interno enviado por FastAPI
		operacion = respuesta_servidor["operacion"]
		nombre_operacion = operacion.get("nombre", "")
		
		# Se agregaron las comillas a 'diferencia' para evitar NameError
		diferencia = operacion.get("diferencia", 0)
		
		match nombre_operacion:
			case "AUMENTAR_FLUJO_PULPA":
				self.sensores["flujo_pulpa"].modificar(diferencia)
			
			case "DISMINUIR_FLUJO_PULPA":
				self.sensores["flujo_pulpa"].modificar(-diferencia)
			
			case "AUMENTAR_FLUJO_CLO2":
				self.sensores["flujo_clo2"].modificar(diferencia)
			
			case "DISMINUIR_FLUJO_CLO2":
				self.sensores["flujo_clo2"].modificar(-diferencia)
			
			case "AUMENTAR_TEMPERATURA":
				self.sensores["temperatura"].modificar(diferencia)
			
			case "DISMINUIR_TEMPERATURA":
				self.sensores["temperatura"].modificar(-diferencia)
			
			case "ACTIVAR_VALVULA_ALIVIO":
				self.sensores["presion"].modificar(-35.0)
		
		return
	
	def actualizar(self):
		for sensor in self.sensores.keys():
			self.sensores[sensor].actualizar()
		
		return