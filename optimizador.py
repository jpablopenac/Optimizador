"""
Módulo de Optimización de Transporte Universitario
===================================================
Sistema de optimización en dos etapas:
    - Etapa 1: Consolidación de demanda usando flexibilidad de usuarios
    - Etapa 2: Asignación óptima de conductores usando PuLP

Reglas de Flexibilidad:
    - Flex_Ida: Usuario puede moverse 1 bloque ANTES (ej: 11:00→9:40)
    - Flex_Vuelta: Usuario puede moverse 1 bloque DESPUÉS (ej: 16:00→17:20)
    - Voluntario_Segundo_Viaje: Conductor puede hacer 2 viajes en la SEMANA

Autor: Sistema de Optimización
Fecha: 2026
"""

import pandas as pd
import numpy as np
import logging
from pulp import *
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
from copy import deepcopy


# =============================================================================
# CONFIGURACIÓN DE LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURACIÓN GLOBAL
# =============================================================================

DIAS = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes']
HORARIOS_IDA = ['8:20', '9:40', '11:00', '12:20']
HORARIOS_VUELTA = ['13:30', '16:00', '17:20', '18:40']
# Capacidad = pasajeros que puede llevar cada conductor (sin contarlo a él)
# Auto con 5 asientos: 1 conductor + 4 pasajeros = CAPACIDAD_VEHICULO = 4
CAPACIDAD_VEHICULO = 4


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class Usuario:
    """Representa un usuario del sistema"""
    nombre: str
    horario_original: str
    horario_asignado: str
    es_flexible: bool
    es_conductor: bool
    fue_movido: bool = False


@dataclass 
class BloqueHorario:
    """Representa un bloque de horario específico"""
    dia: str
    horario: str
    tipo: str  # 'ida' o 'vuelta'
    usuarios: List[Usuario] = field(default_factory=list)
    
    @property
    def demanda(self) -> int:
        return len(self.usuarios)
    
    @property
    def usuarios_fijos(self) -> List[Usuario]:
        return [u for u in self.usuarios if not u.es_flexible]
    
    @property
    def usuarios_flexibles(self) -> List[Usuario]:
        return [u for u in self.usuarios if u.es_flexible]
    
    @property
    def conductores_disponibles(self) -> List[str]:
        return [u.nombre for u in self.usuarios if u.es_conductor]
    
    def agregar_usuario(self, usuario: Usuario):
        self.usuarios.append(usuario)
    
    def remover_usuario(self, nombre: str) -> Optional[Usuario]:
        for i, u in enumerate(self.usuarios):
            if u.nombre == nombre:
                return self.usuarios.pop(i)
        return None


@dataclass
class ResultadoOptimizacion:
    """Resultado de la optimización para un bloque"""
    dia: str
    horario: str
    tipo: str
    demanda_total: int
    usuarios_fijos: int
    usuarios_movidos: int
    conductores_asignados: List[str]
    pasajeros_cubiertos: int
    deficit: int
    capacidad_total: int


# =============================================================================
# ETAPA 1: CONSOLIDACIÓN DE DEMANDA POR DENSIDAD
# =============================================================================

class ConsolidadorDemanda:
    """
    Etapa 1: Consolida la demanda moviendo usuarios flexibles a bloques más densos.
    
    Reglas:
    - Flex_Ida: Puede mover 1 bloque ANTES (índice menor en HORARIOS_IDA)
    - Flex_Vuelta: Puede mover 1 bloque DESPUÉS (índice mayor en HORARIOS_VUELTA)
    - Objetivo: Maximizar la concentración de usuarios en pocos bloques
    """
    
    def __init__(self, datos: pd.DataFrame):
        self.datos = datos
        self.bloques_ida: Dict[str, Dict[str, BloqueHorario]] = {}
        self.bloques_vuelta: Dict[str, Dict[str, BloqueHorario]] = {}
        self.voluntarios_segundo_viaje: Set[str] = set()
        self.conductores_por_dia: Dict[str, Set[str]] = defaultdict(set)
        self.movimientos_realizados: List[Dict] = []
        
        # NUEVO: Para la Regla de Oro
        self.todos_usuarios: Set[str] = set()  # TODOS los que usan el sistema
        self.disponibilidad_conductor: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)  # {usuario: [(dia, horario, tipo), ...]}
        
    def ejecutar(self) -> Tuple[Dict, Dict]:
        """
        Ejecuta la consolidación completa.
        
        Returns:
            Tupla con (bloques_ida, bloques_vuelta) ya consolidados
        """
        self._inicializar_bloques()
        self._poblar_bloques()
        self._consolidar_flexibles()
        return self.bloques_ida, self.bloques_vuelta
    
    def _inicializar_bloques(self):
        """Inicializa la estructura de bloques vacíos"""
        for dia in DIAS:
            self.bloques_ida[dia] = {}
            self.bloques_vuelta[dia] = {}
            
            for horario in HORARIOS_IDA:
                self.bloques_ida[dia][horario] = BloqueHorario(
                    dia=dia, horario=horario, tipo='ida'
                )
            
            for horario in HORARIOS_VUELTA:
                self.bloques_vuelta[dia][horario] = BloqueHorario(
                    dia=dia, horario=horario, tipo='vuelta'
                )
    
    def _es_booleano_positivo(self, valor) -> bool:
        """Verifica si un valor representa True/Si"""
        if pd.isna(valor):
            return False
        return str(valor).strip().lower() in ['si', 'sí', 'yes', '1', 'true']
    
    def _poblar_bloques(self):
        """Pobla los bloques con datos de usuarios del CSV"""
        for _, row in self.datos.iterrows():
            nombre = row['Nombre']
            
            # Registrar usuario en el sistema
            self.todos_usuarios.add(nombre)
            
            # Verificar si es voluntario para segundo viaje
            if self._es_booleano_positivo(row.get('Voluntario_Segundo_Viaje', '')):
                self.voluntarios_segundo_viaje.add(nombre)
            
            for dia in DIAS:
                es_conductor = self._es_booleano_positivo(row.get(f'{dia}_Conductor', ''))
                
                # Procesar IDA
                horario_ida = str(row.get(f'{dia}_Ida', '')).strip()
                if horario_ida and horario_ida in HORARIOS_IDA:
                    es_flex = self._es_booleano_positivo(row.get(f'{dia}_Flex_Ida', ''))
                    
                    usuario = Usuario(
                        nombre=nombre,
                        horario_original=horario_ida,
                        horario_asignado=horario_ida,
                        es_flexible=es_flex,
                        es_conductor=es_conductor
                    )
                    self.bloques_ida[dia][horario_ida].agregar_usuario(usuario)
                    
                    # Registrar disponibilidad como conductor para ida
                    if es_conductor:
                        self.conductores_por_dia[dia].add(nombre)
                        self.disponibilidad_conductor[nombre].append((dia, horario_ida, 'ida'))
                
                # Procesar VUELTA
                horario_vuelta = str(row.get(f'{dia}_Vuelta', '')).strip()
                if horario_vuelta and horario_vuelta in HORARIOS_VUELTA:
                    es_flex = self._es_booleano_positivo(row.get(f'{dia}_Flex_Vuelta', ''))
                    
                    usuario = Usuario(
                        nombre=nombre,
                        horario_original=horario_vuelta,
                        horario_asignado=horario_vuelta,
                        es_flexible=es_flex,
                        es_conductor=es_conductor
                    )
                    self.bloques_vuelta[dia][horario_vuelta].agregar_usuario(usuario)
                    
                    # Registrar disponibilidad como conductor para vuelta
                    if es_conductor:
                        self.disponibilidad_conductor[nombre].append((dia, horario_vuelta, 'vuelta'))
    
    def _obtener_horario_destino_ida(self, horario_actual: str) -> Optional[str]:
        """
        Para IDA: Retorna el horario 1 bloque ANTES (más temprano).
        Ej: 11:00 -> 9:40, 9:40 -> 8:20
        """
        idx = HORARIOS_IDA.index(horario_actual)
        if idx > 0:  # Puede moverse hacia atrás
            return HORARIOS_IDA[idx - 1]
        return None  # Ya está en el primer horario
    
    def _obtener_horario_destino_vuelta(self, horario_actual: str) -> Optional[str]:
        """
        Para VUELTA: Retorna el horario 1 bloque DESPUÉS (más tarde).
        Ej: 16:00 -> 17:20, 17:20 -> 18:40
        """
        idx = HORARIOS_VUELTA.index(horario_actual)
        if idx < len(HORARIOS_VUELTA) - 1:  # Puede moverse hacia adelante
            return HORARIOS_VUELTA[idx + 1]
        return None  # Ya está en el último horario
    
    def _consolidar_flexibles(self):
        """
        Consolida usuarios flexibles en bloques de mayor densidad.
        Usa PuLP para optimizar las decisiones de movimiento.
        """
        for dia in DIAS:
            self._consolidar_dia(dia, 'ida')
            self._consolidar_dia(dia, 'vuelta')
    
    def _consolidar_dia(self, dia: str, tipo: str):
        """
        Optimiza la consolidación de un día/tipo específico usando PuLP.
        
        Objetivo: Mover usuarios flexibles para maximizar la densidad
        de los bloques más poblados (minimizar fragmentación).
        """
        bloques = self.bloques_ida[dia] if tipo == 'ida' else self.bloques_vuelta[dia]
        horarios = HORARIOS_IDA if tipo == 'ida' else HORARIOS_VUELTA
        
        # Recopilar usuarios flexibles que pueden moverse
        usuarios_movibles = []  # (nombre, horario_origen, horario_destino)
        
        for horario in horarios:
            bloque = bloques[horario]
            for usuario in bloque.usuarios_flexibles:
                if tipo == 'ida':
                    destino = self._obtener_horario_destino_ida(horario)
                else:
                    destino = self._obtener_horario_destino_vuelta(horario)
                
                if destino:
                    usuarios_movibles.append((usuario.nombre, horario, destino))
        
        if not usuarios_movibles:
            return  # No hay usuarios que mover
        
        # Crear problema de optimización
        problema = LpProblem(f"Consolidar_{dia}_{tipo}", LpMaximize)
        
        # Variables de decisión: mover[i] = 1 si el usuario i se mueve
        mover = LpVariable.dicts(
            "mover",
            range(len(usuarios_movibles)),
            cat='Binary'
        )
        
        # Calcular el beneficio de mover cada usuario
        # Beneficio = demanda del bloque destino (queremos mover hacia bloques más densos)
        demanda_destino = []
        for _, _, destino in usuarios_movibles:
            demanda_destino.append(bloques[destino].demanda)
        
        # FUNCIÓN OBJETIVO: Maximizar movimientos hacia bloques densos
        # Ponderamos por la demanda del destino para priorizar consolidación
        problema += lpSum([
            mover[i] * (demanda_destino[i] + 1)  # +1 para que siempre valga mover
            for i in range(len(usuarios_movibles))
        ]), "Maximizar_Consolidacion"
        
        # RESTRICCIÓN: Evitar que un bloque quede vacío si tiene usuarios fijos
        # No se necesita restricción adicional porque solo movemos flexibles
        
        # RESTRICCIÓN: No mover conductores si el bloque origen los necesita más
        # (Opcional: mantener conductores en sus horarios originales)
        for i, (nombre, origen, _) in enumerate(usuarios_movibles):
            bloque_origen = bloques[origen]
            usuario = next((u for u in bloque_origen.usuarios if u.nombre == nombre), None)
            if usuario and usuario.es_conductor:
                # Si es el único conductor en origen, no moverlo
                conductores_en_origen = len(bloque_origen.conductores_disponibles)
                if conductores_en_origen <= 1:
                    problema += mover[i] == 0, f"Mantener_Conductor_{i}"
        
        # Resolver
        problema.solve(PULP_CBC_CMD(msg=0))
        
        # Aplicar movimientos
        for i, (nombre, origen, destino) in enumerate(usuarios_movibles):
            if value(mover[i]) == 1:
                # Mover usuario
                bloque_origen = bloques[origen]
                bloque_destino = bloques[destino]
                
                usuario = bloque_origen.remover_usuario(nombre)
                if usuario:
                    usuario.horario_asignado = destino
                    usuario.fue_movido = True
                    bloque_destino.agregar_usuario(usuario)
                    
                    # IMPORTANTE: Actualizar disponibilidad como conductor si aplica
                    if usuario.es_conductor and nombre in self.disponibilidad_conductor:
                        old_slot = (dia, origen, tipo)
                        new_slot = (dia, destino, tipo)
                        if old_slot in self.disponibilidad_conductor[nombre]:
                            self.disponibilidad_conductor[nombre].remove(old_slot)
                            self.disponibilidad_conductor[nombre].append(new_slot)
                            logger.debug(f"Actualizada disponibilidad de {nombre}: {old_slot} -> {new_slot}")
                    
                    self.movimientos_realizados.append({
                        'usuario': nombre,
                        'dia': dia,
                        'tipo': tipo,
                        'origen': origen,
                        'destino': destino
                    })
    
    def obtener_estadisticas(self) -> Dict:
        """Retorna estadísticas del análisis y consolidación"""
        total_ida = sum(
            self.bloques_ida[d][h].demanda 
            for d in DIAS for h in HORARIOS_IDA
        )
        total_vuelta = sum(
            self.bloques_vuelta[d][h].demanda 
            for d in DIAS for h in HORARIOS_VUELTA
        )
        
        total_conductores = len(set().union(*self.conductores_por_dia.values()) if self.conductores_por_dia else set())
        
        # Contar usuarios flexibles que AÚN NO han sido movidos (disponibles para mover)
        flexibles_ida = sum(
            len([u for u in self.bloques_ida[d][h].usuarios_flexibles if not u.fue_movido])
            for d in DIAS for h in HORARIOS_IDA
        )
        flexibles_vuelta = sum(
            len([u for u in self.bloques_vuelta[d][h].usuarios_flexibles if not u.fue_movido])
            for d in DIAS for h in HORARIOS_VUELTA
        )
        
        # Total de usuarios que FUERON movidos
        usuarios_movidos_ida = sum(
            len([u for u in self.bloques_ida[d][h].usuarios if u.fue_movido])
            for d in DIAS for h in HORARIOS_IDA
        )
        usuarios_movidos_vuelta = sum(
            len([u for u in self.bloques_vuelta[d][h].usuarios if u.fue_movido])
            for d in DIAS for h in HORARIOS_VUELTA
        )
        
        # Usuarios sin disponibilidad como conductor (PROBLEMA para la Regla de Oro)
        usuarios_sin_disponibilidad = [
            u for u in self.todos_usuarios 
            if u not in self.disponibilidad_conductor or len(self.disponibilidad_conductor[u]) == 0
        ]
        
        # Usuarios con solo 1 día disponible (deben manejar ese día sí o sí)
        # Nota: disponibilidad_conductor contiene slots (dia, horario, tipo), hay que contar días únicos
        usuarios_un_solo_dia = [
            u for u in self.todos_usuarios 
            if u in self.disponibilidad_conductor and len(set(slot[0] for slot in self.disponibilidad_conductor[u])) == 1
        ]
        
        return {
            'total_usuarios': len(self.todos_usuarios),
            'total_registros_ida': total_ida,
            'total_registros_vuelta': total_vuelta,
            'total_conductores_unicos': total_conductores,
            'voluntarios_segundo_viaje': len(self.voluntarios_segundo_viaje),
            'usuarios_flexibles_ida': flexibles_ida,  # Flexibles que AÚN pueden moverse
            'usuarios_flexibles_vuelta': flexibles_vuelta,
            'usuarios_movidos_ida': usuarios_movidos_ida,  # Ya fueron movidos
            'usuarios_movidos_vuelta': usuarios_movidos_vuelta,
            'movimientos_realizados': len(self.movimientos_realizados),
            'horario_pico_ida': self._obtener_horario_pico('ida'),
            'horario_pico_vuelta': self._obtener_horario_pico('vuelta'),
            'usuarios_sin_disponibilidad': usuarios_sin_disponibilidad,
            'total_sin_disponibilidad': len(usuarios_sin_disponibilidad),
            'usuarios_un_solo_dia': usuarios_un_solo_dia,
            'total_un_solo_dia': len(usuarios_un_solo_dia),
        }
    
    def _obtener_horario_pico(self, tipo: str) -> Optional[Tuple[str, str, int]]:
        """Obtiene el horario con mayor demanda después de consolidación"""
        bloques = self.bloques_ida if tipo == 'ida' else self.bloques_vuelta
        horarios = HORARIOS_IDA if tipo == 'ida' else HORARIOS_VUELTA
        
        max_demanda = 0
        pico = None
        
        for dia in DIAS:
            for horario in horarios:
                demanda = bloques[dia][horario].demanda
                if demanda > max_demanda:
                    max_demanda = demanda
                    pico = (dia, horario, demanda)
        
        return pico
    
    def generar_heatmap_data(self) -> Dict:
        """Genera datos para visualización de heatmaps"""
        matriz_ida = pd.DataFrame(index=HORARIOS_IDA, columns=DIAS, dtype=int).fillna(0)
        matriz_vuelta = pd.DataFrame(index=HORARIOS_VUELTA, columns=DIAS, dtype=int).fillna(0)
        
        for dia in DIAS:
            for horario in HORARIOS_IDA:
                matriz_ida.loc[horario, dia] = self.bloques_ida[dia][horario].demanda
            for horario in HORARIOS_VUELTA:
                matriz_vuelta.loc[horario, dia] = self.bloques_vuelta[dia][horario].demanda
        
        return {
            'ida': {
                'datos': matriz_ida.values.tolist(),
                'filas': HORARIOS_IDA,
                'columnas': DIAS,
                'max_valor': int(matriz_ida.max().max()) if not matriz_ida.empty else 0
            },
            'vuelta': {
                'datos': matriz_vuelta.values.tolist(),
                'filas': HORARIOS_VUELTA,
                'columnas': DIAS,
                'max_valor': int(matriz_vuelta.max().max()) if not matriz_vuelta.empty else 0
            }
        }
    
    def obtener_bloques_ordenados(self, tipo: str = 'ida') -> List[BloqueHorario]:
        """Retorna bloques ordenados por demanda (mayor a menor)"""
        bloques = self.bloques_ida if tipo == 'ida' else self.bloques_vuelta
        todos = []
        
        for dia in DIAS:
            for horario, bloque in bloques[dia].items():
                if bloque.demanda > 0:
                    todos.append(bloque)
        
        return sorted(todos, key=lambda x: x.demanda, reverse=True)


# =============================================================================
# ETAPA 2: ASIGNACIÓN ÓPTIMA DE CONDUCTORES CON PULP
# =============================================================================

class OptimizadorConductores:
    """
    Etapa 2: Optimiza la asignación de conductores usando Programación Lineal.
    
    REGLA DE ORO: Para ser pasajero, DEBES manejar mínimo 1 día a la semana.
    La "forma de pago" es manejar. No puedes ser solo pasajero.
    
    Considera:
    - TODOS los usuarios deben manejar mínimo 1 vez por semana
    - Voluntario_Segundo_Viaje: Puede conducir hasta 2 veces en la SEMANA
    - Usuarios normales: Exactamente 1 vez por semana (mínimo obligatorio)
    - Optimización global de toda la semana
    """
    
    def __init__(self, bloques_ida: Dict, bloques_vuelta: Dict,
                 todos_usuarios: Set[str],
                 disponibilidad_conductor: Dict[str, List[Tuple[str, str, str]]],
                 voluntarios_segundo_viaje: Set[str],
                 capacidad_vehiculo: int = CAPACIDAD_VEHICULO):
        self.bloques_ida = bloques_ida
        self.bloques_vuelta = bloques_vuelta
        self.todos_usuarios = todos_usuarios  # TODOS los que quieren usar el sistema
        self.disponibilidad = disponibilidad_conductor  # {usuario: [(dia, horario, tipo), ...]}
        self.voluntarios = voluntarios_segundo_viaje
        self.capacidad = capacidad_vehiculo
        self.resultados: List[ResultadoOptimizacion] = []
        self.estado_solucion = None
        self.razon_infactible = None  # Explicación si el problema no tiene solución
        self.asignaciones_conductor: Dict[str, List[Dict]] = defaultdict(list)
        self.usuarios_sin_disponibilidad: List[str] = []  # Usuarios que no pueden manejar ningún día
        self.usuarios_un_solo_dia: List[str] = []  # Usuarios que solo pueden manejar 1 día (DEBEN manejar ese día)
        
    def optimizar(self) -> List[ResultadoOptimizacion]:
        """
        Ejecuta la optimización global de toda la semana.
        
        REGLA DE ORO: Todos deben manejar mínimo 1 vez para poder ser pasajeros.
        
        Returns:
            Lista de resultados de optimización por bloque
        """
        self.resultados = []
        
        # Construir lista de slots con demanda
        slots = []  # Lista de (dia, horario, tipo, bloque)
        
        for dia in DIAS:
            for horario in HORARIOS_IDA:
                bloque = self.bloques_ida[dia][horario]
                if bloque.demanda > 0:
                    slots.append((dia, horario, 'ida', bloque))
            
            for horario in HORARIOS_VUELTA:
                bloque = self.bloques_vuelta[dia][horario]
                if bloque.demanda > 0:
                    slots.append((dia, horario, 'vuelta', bloque))
        
        # Identificar usuarios sin disponibilidad para manejar (PROBLEMA - no pueden participar)
        self.usuarios_sin_disponibilidad = [
            u for u in self.todos_usuarios 
            if u not in self.disponibilidad or len(self.disponibilidad[u]) == 0
        ]
        
        # Identificar usuarios con solo 1 día disponible (OBLIGADOS a manejar ese día)
        # Nota: disponibilidad contiene slots (dia, horario, tipo), hay que contar días únicos
        self.usuarios_un_solo_dia = [
            u for u in self.todos_usuarios 
            if u in self.disponibilidad and len(set(slot[0] for slot in self.disponibilidad[u])) == 1
        ]
        
        # Solo consideramos usuarios que SÍ pueden manejar
        usuarios_validos = [u for u in self.todos_usuarios if u in self.disponibilidad and len(self.disponibilidad[u]) > 0]
        
        if not usuarios_validos or not slots:
            for dia, horario, tipo, bloque in slots:
                self.resultados.append(ResultadoOptimizacion(
                    dia=dia, horario=horario, tipo=tipo,
                    demanda_total=bloque.demanda,
                    usuarios_fijos=len(bloque.usuarios_fijos),
                    usuarios_movidos=sum(1 for u in bloque.usuarios if u.fue_movido),
                    conductores_asignados=[],
                    pasajeros_cubiertos=0,
                    deficit=bloque.demanda,
                    capacidad_total=0
                ))
            return self.resultados
        
        # Crear problema de optimización GLOBAL
        problema = LpProblem("Asignacion_Semanal", LpMaximize)
        
        # Variables de decisión: x[usuario, slot_idx] = 1 si usuario maneja en ese slot
        x = LpVariable.dicts(
            "asignacion",
            [(u, i) for u in usuarios_validos for i in range(len(slots))],
            cat='Binary'
        )
        
        # Variables auxiliares: pasajeros cubiertos por slot
        pasajeros = LpVariable.dicts(
            "pasajeros",
            range(len(slots)),
            lowBound=0,
            cat='Integer'
        )
        
        # FUNCIÓN OBJETIVO: Maximizar pasajeros cubiertos
        problema += lpSum([pasajeros[i] for i in range(len(slots))]), "Maximizar_Cobertura"
        
        # =====================================================================
        # REGLA DE ORO: TODOS deben manejar mínimo 1 vez a la semana
        # =====================================================================
        for u in usuarios_validos:
            problema += (
                lpSum([x[(u, i)] for i in range(len(slots))]) >= 1,
                f"Minimo_Un_Viaje_{u}"
            )
        
        # RESTRICCIÓN 2: Límite MÁXIMO de viajes por usuario
        for u in usuarios_validos:
            max_viajes = 2 if u in self.voluntarios else 1
            problema += (
                lpSum([x[(u, i)] for i in range(len(slots))]) <= max_viajes,
                f"Max_Viajes_{u}"
            )
        
        # RESTRICCIÓN 3: Usuario solo puede asignarse donde tiene disponibilidad
        for u in usuarios_validos:
            disponibles_usuario = set(self.disponibilidad.get(u, []))
            for i, (dia, horario, tipo, bloque) in enumerate(slots):
                slot_key = (dia, horario, tipo)
                if slot_key not in disponibles_usuario:
                    problema += x[(u, i)] == 0, f"Disponibilidad_{u}_{i}"
        
        # RESTRICCIÓN 4: Pasajeros cubiertos <= capacidad * conductores asignados
        # Cada conductor cubre: él mismo + CAPACIDAD pasajeros = (CAPACIDAD + 1) personas
        for i in range(len(slots)):
            problema += (
                pasajeros[i] <= (self.capacidad + 1) * lpSum([x[(u, i)] for u in usuarios_validos]),
                f"Capacidad_{i}"
            )
        
        # RESTRICCIÓN 5: Pasajeros cubiertos <= demanda real
        for i, (_, _, _, bloque) in enumerate(slots):
            problema += pasajeros[i] <= bloque.demanda, f"Demanda_{i}"
        
        # Resolver
        problema.solve(PULP_CBC_CMD(msg=0))
        self.estado_solucion = LpStatus[problema.status]
        
        # Detectar problema INFACTIBLE y dar explicación
        if self.estado_solucion == 'Infeasible':
            # Calcular métricas para explicar por qué es infactible
            total_slots_disponibles = sum(len(self.disponibilidad.get(u, [])) for u in usuarios_validos)
            logger.warning(f"PROBLEMA INFACTIBLE: {len(usuarios_validos)} usuarios deben manejar >= 1 vez")
            logger.warning(f"Total slots disponibles en el sistema: {total_slots_disponibles}")
            logger.warning(f"Slots con demanda: {len(slots)}")
            
            # Identificar usuarios problemáticos (con muy pocos slots disponibles)
            usuarios_problematicos = [
                (u, len(self.disponibilidad.get(u, []))) 
                for u in usuarios_validos 
                if len(self.disponibilidad.get(u, [])) <= 2
            ]
            if usuarios_problematicos:
                logger.warning(f"Usuarios con poca disponibilidad: {usuarios_problematicos}")
            
            self.razon_infactible = (
                f"No es posible asignar a todos los {len(usuarios_validos)} usuarios. "
                f"Hay {len(slots)} slots con demanda pero la disponibilidad de conductores es insuficiente. "
                f"Considera: agregar más días de disponibilidad o permitir que algunos no manejen."
            )
            
            # Retornar resultados vacíos pero con información
            for dia, horario, tipo, bloque in slots:
                self.resultados.append(ResultadoOptimizacion(
                    dia=dia, horario=horario, tipo=tipo,
                    demanda_total=bloque.demanda,
                    usuarios_fijos=len(bloque.usuarios_fijos),
                    usuarios_movidos=sum(1 for u in bloque.usuarios if u.fue_movido),
                    conductores_asignados=[],
                    pasajeros_cubiertos=0,
                    deficit=bloque.demanda,
                    capacidad_total=0
                ))
            return self.resultados
        
        # Procesar resultados
        for i, (dia, horario, tipo, bloque) in enumerate(slots):
            conductores_asignados = [u for u in usuarios_validos if value(x[(u, i)]) == 1]
            
            # Registrar asignaciones por conductor
            for u in conductores_asignados:
                self.asignaciones_conductor[u].append({
                    'dia': dia, 'horario': horario, 'tipo': tipo
                })
            
            # Capacidad total: cada conductor cubre él mismo + CAPACIDAD pasajeros
            capacidad_total = len(conductores_asignados) * (self.capacidad + 1)
            
            # Cálculo robusto de pasajeros cubiertos
            pax_valor = value(pasajeros[i])
            pax_cubiertos = min(int(pax_valor) if pax_valor is not None else 0, bloque.demanda)
            
            self.resultados.append(ResultadoOptimizacion(
                dia=dia,
                horario=horario,
                tipo=tipo,
                demanda_total=bloque.demanda,
                usuarios_fijos=len(bloque.usuarios_fijos),
                usuarios_movidos=sum(1 for u in bloque.usuarios if u.fue_movido),
                conductores_asignados=conductores_asignados,
                pasajeros_cubiertos=pax_cubiertos,
                deficit=max(0, bloque.demanda - capacidad_total),
                capacidad_total=capacidad_total
            ))
        
        return self.resultados
    
    def obtener_resumen(self) -> Dict:
        """Genera un resumen de la optimización"""
        if not self.resultados:
            return {}
        
        total_demanda = sum(r.demanda_total for r in self.resultados)
        total_cubiertos = sum(r.pasajeros_cubiertos for r in self.resultados)
        total_deficit = sum(r.deficit for r in self.resultados)
        
        conductores_unicos = set(c for r in self.resultados for c in r.conductores_asignados)
        conductores_doble_viaje = [c for c in conductores_unicos if len(self.asignaciones_conductor[c]) == 2]
        
        # Por día
        por_dia = defaultdict(lambda: {'demanda': 0, 'cubiertos': 0, 'deficit': 0, 'conductores': set()})
        for r in self.resultados:
            por_dia[r.dia]['demanda'] += r.demanda_total
            por_dia[r.dia]['cubiertos'] += r.pasajeros_cubiertos
            por_dia[r.dia]['deficit'] += r.deficit
            por_dia[r.dia]['conductores'].update(r.conductores_asignados)
        
        resumen_dias = {}
        for dia, datos in por_dia.items():
            resumen_dias[dia] = {
                'demanda': datos['demanda'],
                'cubiertos': datos['cubiertos'],
                'deficit': datos['deficit'],
                'conductores': len(datos['conductores']),
                'cobertura_pct': round(datos['cubiertos'] / datos['demanda'] * 100, 1) if datos['demanda'] > 0 else 0
            }
        
        # Usuarios que manejan exactamente 1 vez (cumplieron el mínimo)
        usuarios_un_viaje = [c for c in conductores_unicos if len(self.asignaciones_conductor[c]) == 1]
        
        return {
            'estado_solucion': self.estado_solucion,
            'razon_infactible': self.razon_infactible,
            'total_demanda': total_demanda,
            'total_cubiertos': total_cubiertos,
            'total_deficit': total_deficit,
            'total_conductores_asignados': len(conductores_unicos),
            'usuarios_un_viaje': len(usuarios_un_viaje),
            'conductores_doble_viaje': len(conductores_doble_viaje),
            'detalle_un_viaje': {c: self.asignaciones_conductor[c] for c in usuarios_un_viaje},
            'detalle_doble_viaje': {c: self.asignaciones_conductor[c] for c in conductores_doble_viaje},
            'usuarios_sin_disponibilidad': self.usuarios_sin_disponibilidad,
            'usuarios_un_solo_dia': self.usuarios_un_solo_dia,
            'cobertura_global_pct': round(total_cubiertos / total_demanda * 100, 1) if total_demanda > 0 else 0,
            'por_dia': resumen_dias
        }
    
    def obtener_grid_resultados(self) -> Dict:
        """Genera estructura de grid para visualización"""
        grid = {dia: {'ida': {}, 'vuelta': {}} for dia in DIAS}
        
        for r in self.resultados:
            grid[r.dia][r.tipo][r.horario] = {
                'demanda': r.demanda_total,
                'usuarios_fijos': r.usuarios_fijos,
                'usuarios_movidos': r.usuarios_movidos,
                'conductores': r.conductores_asignados,
                'num_conductores': len(r.conductores_asignados),
                'capacidad': r.capacidad_total,
                'cubiertos': r.pasajeros_cubiertos,
                'deficit': r.deficit,
                'estado': 'ok' if r.deficit == 0 else ('alerta' if r.deficit <= 2 else 'critico')
            }
        
        return grid


# =============================================================================
# FUNCIÓN PRINCIPAL DE EJECUCIÓN
# =============================================================================

def ejecutar_optimizacion(archivo_csv: str, capacidad: int = CAPACIDAD_VEHICULO) -> Dict:
    """
    Función principal que ejecuta el pipeline completo de optimización.
    
    Etapa 1: Consolida demanda moviendo usuarios flexibles
    Etapa 2: Asigna conductores óptimamente (considerando voluntarios segundo viaje)
    
    Args:
        archivo_csv: Ruta al archivo CSV con los datos
        capacidad: Capacidad de cada vehículo
        
    Returns:
        Diccionario con todos los resultados de la optimización
    """
    # Cargar datos
    try:
        datos = pd.read_csv(archivo_csv, encoding='utf-8')
    except FileNotFoundError:
        return {'error': 'Archivo no encontrado', 'exito': False}
    except Exception as e:
        return {'error': f'Error al leer archivo: {str(e)}', 'exito': False}
    
    if datos.empty or len(datos) == 0:
        return {'error': 'No hay datos para optimizar', 'exito': False}
    
    # Eliminar duplicados: si hay 2+ registros con el mismo nombre, mantener el más reciente
    if 'Nombre' in datos.columns:
        duplicados_antes = len(datos)
        # Ordenar por Timestamp (más reciente primero) si existe, luego eliminar duplicados por Nombre
        if 'Timestamp' in datos.columns:
            datos = datos.sort_values('Timestamp', ascending=False)
        datos = datos.drop_duplicates(subset=['Nombre'], keep='first')
        duplicados_eliminados = duplicados_antes - len(datos)
        if duplicados_eliminados > 0:
            logger.warning(f"Se eliminaron {duplicados_eliminados} registros duplicados (se mantuvo el más reciente por nombre)")
    
    # Verificar que hay al menos una columna de horario con datos
    tiene_datos = False
    for dia in DIAS:
        col_ida = f'{dia}_Ida'
        col_vuelta = f'{dia}_Vuelta'
        if col_ida in datos.columns and datos[col_ida].notna().any():
            tiene_datos = True
            break
        if col_vuelta in datos.columns and datos[col_vuelta].notna().any():
            tiene_datos = True
            break
    
    if not tiene_datos:
        return {'error': 'No hay datos de horarios para optimizar', 'exito': False}
    
    # ETAPA 1: Consolidación de Demanda
    consolidador = ConsolidadorDemanda(datos)
    bloques_ida, bloques_vuelta = consolidador.ejecutar()
    
    estadisticas = consolidador.obtener_estadisticas()
    heatmap_data = consolidador.generar_heatmap_data()
    movimientos = consolidador.movimientos_realizados
    
    bloques_densos_ida = consolidador.obtener_bloques_ordenados('ida')
    bloques_densos_vuelta = consolidador.obtener_bloques_ordenados('vuelta')
    
    # ETAPA 2: Optimización de Conductores (con REGLA DE ORO)
    optimizador = OptimizadorConductores(
        bloques_ida, bloques_vuelta,
        consolidador.todos_usuarios,  # TODOS los usuarios del sistema
        consolidador.disponibilidad_conductor,  # Disponibilidad de cada uno como conductor
        consolidador.voluntarios_segundo_viaje,
        capacidad
    )
    resultados = optimizador.optimizar()
    
    resumen = optimizador.obtener_resumen()
    grid_resultados = optimizador.obtener_grid_resultados()
    
    return {
        'exito': True,
        'total_usuarios': len(datos),
        
        # Resultados Etapa 1: Consolidación
        'densidad': {
            'estadisticas': estadisticas,
            'heatmap_data': heatmap_data,
            'movimientos_flexibles': movimientos,
            'total_movimientos': len(movimientos),
            'bloques_densos_ida': [
                {
                    'dia': b.dia, 
                    'horario': b.horario, 
                    'demanda': b.demanda,
                    'usuarios_fijos': len(b.usuarios_fijos),
                    'usuarios_movidos': sum(1 for u in b.usuarios if u.fue_movido),
                    'conductores': len(b.conductores_disponibles)
                }
                for b in bloques_densos_ida[:5]
            ],
            'bloques_densos_vuelta': [
                {
                    'dia': b.dia, 
                    'horario': b.horario, 
                    'demanda': b.demanda,
                    'usuarios_fijos': len(b.usuarios_fijos),
                    'usuarios_movidos': sum(1 for u in b.usuarios if u.fue_movido),
                    'conductores': len(b.conductores_disponibles)
                }
                for b in bloques_densos_vuelta[:5]
            ]
        },
        
        # Resultados Etapa 2: Asignación de Conductores
        'conductores': {
            'resumen': resumen,
            'grid_resultados': grid_resultados,
            'detalles': [
                {
                    'dia': r.dia,
                    'horario': r.horario,
                    'tipo': r.tipo,
                    'demanda': r.demanda_total,
                    'usuarios_fijos': r.usuarios_fijos,
                    'usuarios_movidos': r.usuarios_movidos,
                    'conductores': r.conductores_asignados,
                    'capacidad': r.capacidad_total,
                    'cubiertos': r.pasajeros_cubiertos,
                    'deficit': r.deficit
                }
                for r in resultados
            ]
        }
    }


# =============================================================================
# EJECUCIÓN DIRECTA PARA PRUEBAS
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("SISTEMA DE OPTIMIZACIÓN DE TRANSPORTE UNIVERSITARIO")
    print("=" * 70)
    
    resultado = ejecutar_optimizacion('datos_usuarios.csv')
    
    if resultado.get('exito'):
        print(f"\n✓ Optimización completada para {resultado['total_usuarios']} usuarios")
        
        print("\n" + "-" * 70)
        print("ETAPA 1: CONSOLIDACIÓN DE DEMANDA")
        print("-" * 70)
        stats = resultado['densidad']['estadisticas']
        print(f"  Total usuarios:            {stats['total_usuarios']}")
        print(f"  Total registros (ida):     {stats['total_registros_ida']}")
        print(f"  Total registros (vuelta):  {stats['total_registros_vuelta']}")
        print(f"  Conductores únicos:        {stats['total_conductores_unicos']}")
        print(f"  Voluntarios 2do viaje:     {stats['voluntarios_segundo_viaje']}")
        print(f"  Usuarios movidos (ida):    {stats.get('usuarios_movidos_ida', 0)}")
        print(f"  Usuarios movidos (vuelta): {stats.get('usuarios_movidos_vuelta', 0)}")
        print(f"  Flexibles restantes (ida): {stats['usuarios_flexibles_ida']}")
        print(f"  Flexibles restantes (vuelta): {stats['usuarios_flexibles_vuelta']}")
        print(f"  Movimientos realizados:    {stats['movimientos_realizados']}")
        
        # Alertar sobre usuarios sin disponibilidad
        if stats.get('total_sin_disponibilidad', 0) > 0:
            print(f"\n  ⚠️  ALERTA: {stats['total_sin_disponibilidad']} usuario(s) SIN disponibilidad para manejar:")
            for u in stats['usuarios_sin_disponibilidad']:
                print(f"      ✗ {u} - No puede participar (Regla de Oro)")
        
        if resultado['densidad']['movimientos_flexibles']:
            print("\n  Movimientos de usuarios flexibles:")
            for mov in resultado['densidad']['movimientos_flexibles'][:10]:
                print(f"    • {mov['usuario']}: {mov['dia']} {mov['tipo']} {mov['origen']} → {mov['destino']}")
        
        print("\n" + "-" * 70)
        print("ETAPA 2: ASIGNACIÓN DE CONDUCTORES (REGLA DE ORO)")
        print("-" * 70)
        print("  Regla: Todos manejan mínimo 1 día para poder ser pasajeros")
        print()
        resumen = resultado['conductores']['resumen']
        print(f"  Estado solución:           {resumen.get('estado_solucion', 'N/A')}")
        
        # Si el problema es infactible, mostrar la razón
        if resumen.get('estado_solucion') == 'Infeasible':
            print(f"\n  ❌ PROBLEMA SIN SOLUCIÓN:")
            print(f"     {resumen.get('razon_infactible', 'Razón desconocida')}")
            print()
        
        print(f"  Demanda total:             {resumen.get('total_demanda', 0)}")
        print(f"  Pasajeros cubiertos:       {resumen.get('total_cubiertos', 0)}")
        print(f"  Déficit:                   {resumen.get('total_deficit', 0)}")
        print(f"  Total conductores:         {resumen.get('total_conductores_asignados', 0)}")
        print(f"  - Con 1 viaje (mínimo):    {resumen.get('usuarios_un_viaje', 0)}")
        print(f"  - Con 2 viajes (voluntarios): {resumen.get('conductores_doble_viaje', 0)}")
        print(f"  Cobertura global:          {resumen.get('cobertura_global_pct', 0)}%")
        
        # Mostrar usuarios sin disponibilidad (PROBLEMA)
        if resumen.get('usuarios_sin_disponibilidad'):
            print(f"\n  ⚠️  USUARIOS EXCLUIDOS (sin disponibilidad para manejar):")
            for u in resumen['usuarios_sin_disponibilidad']:
                print(f"      ✗ {u}")
        
        # Mostrar usuarios con solo 1 día disponible (OBLIGADOS)
        if resumen.get('usuarios_un_solo_dia'):
            print(f"\n  ℹ️  USUARIOS CON SOLO 1 DÍA DISPONIBLE (deben manejar obligatoriamente):")
            for u in resumen['usuarios_un_solo_dia']:
                print(f"      → {u}")
        
        # Mostrar asignaciones de usuarios con 1 viaje
        if resumen.get('detalle_un_viaje'):
            print("\n  Asignaciones (1 viaje - mínimo obligatorio):")
            for c, viajes in resumen['detalle_un_viaje'].items():
                viajes_str = ", ".join([f"{v['dia']} {v['tipo']} {v['horario']}" for v in viajes])
                print(f"    • {c}: {viajes_str}")
        
        # Mostrar asignaciones de voluntarios con 2 viajes
        if resumen.get('detalle_doble_viaje'):
            print("\n  Asignaciones (2 viajes - voluntarios):")
            for c, viajes in resumen['detalle_doble_viaje'].items():
                viajes_str = ", ".join([f"{v['dia']} {v['tipo']} {v['horario']}" for v in viajes])
                print(f"    • {c}: {viajes_str}")
        
        print("\n  Resumen por día:")
        for dia, datos in resumen.get('por_dia', {}).items():
            print(f"    {dia}: Demanda={datos['demanda']}, Cubiertos={datos['cubiertos']}, "
                  f"Déficit={datos['deficit']}, Cobertura={datos['cobertura_pct']}%")
    else:
        print(f"\n✗ Error: {resultado.get('error')}")
