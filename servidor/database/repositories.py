from typing import Optional
from sqlalchemy.orm import Session
from operadores import OperadorRepository, Operador as PydanticOperador, Comando as PydanticComando
from . import models

class SQLOperadorRepository(OperadorRepository):
    def __init__(self, db: Session):
        self.db = db

    def obtener_por_id(self, id_operador: int) -> Optional[PydanticOperador]:
        # Buscamos en la tabla física de la DB
        db_operador = self.db.query(models.Operador).filter(
            models.Operador.id == id_operador
        ).first()
        
        if not db_operador:
            return None
            
        # Transformamos el modelo de SQLAlchemy al modelo Pydantic del dominio
        return PydanticOperador(
            id=db_operador.id,
            nombre=db_operador.nombre,
            email=db_operador.email,
            password_hash=db_operador.password_hash
        )

    def obtener_por_email(self, email: str) -> Optional[PydanticOperador]:
        db_operador = self.db.query(models.Operador).filter(
            models.Operador.email == email
        ).first()
        
        if not db_operador:
            return None
            
        return PydanticOperador(
            id=db_operador.id,
            nombre=db_operador.nombre,
            email=db_operador.email,
            password_hash=db_operador.password_hash
        )


    def registrar_comando(self, comando: PydanticComando) -> PydanticComando:
        # El operador 0 representa al Sistema Central (acciones automáticas) y se almacena directamente
        id_op_db = comando.id_operador

        db_comando = models.Comando(
            id_torre=comando.id_torre,
            id_operador=id_op_db,
            fecha_hora=comando.fecha_hora,
            tipo_instruccion=comando.tipo_instruccion.value if hasattr(comando.tipo_instruccion, "value") else str(comando.tipo_instruccion),
            valor_parametro=comando.valor_parametro,
            estado_ejecucion=comando.estado_ejecucion,
            hash_comando=comando.hash_comando
        )
        
        self.db.add(db_comando)
        self.db.commit()
        self.db.refresh(db_comando)
        
        # Seteamos el ID autogenerado por la BD de vuelta en nuestro objeto Pydantic
        comando.id = db_comando.id
        return comando

class SQLTorreRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def obtener_por_id(self, id_torre: int) -> Optional[models.TorreBlanqueamiento]:
        return self.db.query(models.TorreBlanqueamiento).filter_by(id=id_torre).first()

    def actualizar_estado(self, id_torre: int, estado: str):
        torre = self.obtener_por_id(id_torre)
        if torre:
            torre.estado = estado
            self.db.commit()


class SQLTelemetriaRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def guardar_reporte(self, reporte_dominio) -> models.ReporteTelemetria:
        db_reporte = models.ReporteTelemetria(
            id_torre=reporte_dominio.id_torre,
            ph=reporte_dominio.ph,
            presion=reporte_dominio.presion,
            nivel=reporte_dominio.nivel,
            temperatura=reporte_dominio.temperatura,
            flujo_clo2=reporte_dominio.flujo_clo2,
            flujo_pulpa=reporte_dominio.flujo_pulpa,
            caudal_total=reporte_dominio.caudal_total,
            fecha_hora=reporte_dominio.fecha_hora
        )
        self.db.add(db_reporte)
        self.db.commit()
        self.db.refresh(db_reporte)
        return db_reporte


class SQLAlertaRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def registrar_alerta_proceso(self, id_torre: int, tipo: str, desc: str):
        nueva_alerta = models.AlertaProceso(id_torre=id_torre, tipo_alerta=tipo, descripcion=desc)
        self.db.add(nueva_alerta)
        self.db.commit()
    
    def registrar_alerta_seguridad(self, id_torre: int, tipo_evento: str, origen_ip: Optional[str], payload: Optional[str]):
        nueva_alerta = models.AlertaSeguridad(
            id_torre=id_torre,
            tipo_evento=tipo_evento,
            origen_ip=origen_ip,
            payload_sospechoso=payload
        )
        self.db.add(nueva_alerta)
        self.db.commit()


class SQLComandoRepository:
    def __init__(self, db: Session):
        self.db = db

    def actualizar_estado(self, id_comando: int, nuevo_estado: str):
        db_comando = self.db.query(models.Comando).filter_by(id=id_comando).first()
        if db_comando:
            db_comando.estado_ejecucion = nuevo_estado
            self.db.commit()
            self.db.refresh(db_comando)
        return db_comando