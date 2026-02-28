"""
Módulo de Optimización de Transporte Universitario
===================================================
Este módulo implementa un sistema de optimización en dos etapas:
    - Etapa 1: Análisis de densidad de demanda
    - Etapa 2: Asignación óptima de conductores usando PuLP

Autor: Sistema de Optimización
Fecha: 2026
"""

import pandas as pd
import numpy as np
from pulp import *
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict


# =============================================================================
# CONFIGURACIÓN GLOBAL
# =============================================================================

DIAS = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes']
HORARIOS_IDA = ['8:20', '9:40', '11:00', '12:20']
HORARIOS_VUELTA = ['13:30', '16:00', '17:20', '18:40']
CAPACIDAD_VEHICULO = 4  # Capacidad promedio por vehículo (conductor + 3 pasajeros)


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class BloqueHorario:
    """Representa un bloque de horario específico"""
    dia: str
    horario: str
    tipo: str  # 'ida' o 'vuelta'
    demanda: int
    usuarios: List[str]
    usuarios_flexibles: List[str]
    conductores_disponibles: List[str]


@dataclass
class ResultadoOptimizacion:
    """Resultado de la optimización para un bloque"""
    dia: str
    horario: str
    tipo: str
    demanda_total: int
    conductores_asignados: List[str]
    pasajeros_cubiertos: int
    deficit: int
    capacidad_total: int


# =============================================================================
# ETAPA 1: ANÁLISIS DE DENSIDAD DE DEMANDA
# =============================================================================

class AnalizadorDensidad:
    """
    Etapa 1: Analiza la densidad de demanda por horario y día.
    Agrupa usuarios en bloques de máxima densidad.
    """
    
    def __init__(self, datos: pd.DataFrame):
        """
        Inicializa el analizador con los datos de usuarios.
        
        Args:
            datos: DataFrame con los datos del CSV
        """
        self.datos = datos
        self.bloques_ida: Dict[str, Dict[str, BloqueHorario]] = {}
        self.bloques_vuelta: Dict[str, Dict[str, BloqueHorario]] = {}
        self.matriz_densidad_ida = None
        self.matriz_densidad_vuelta = None
        
    def analizar(self) -> Tuple[Dict, Dict]:
        """
        Ejecuta el análisis completo de densidad.
        
        Returns:
            Tupla con (bloques_ida, bloques_vuelta)
        """
        self._construir_bloques()
        self._calcular_matrices_densidad()
        return self.bloques_ida, self.bloques_vuelta
    
    def _construir_bloques(self):
        """Construye los bloques de horarios con sus usuarios"""
        for dia in DIAS:
            self.bloques_ida[dia] = {}
            self.bloques_vuelta[dia] = {}
            
            for horario in HORARIOS_IDA:
                self.bloques_ida[dia][horario] = BloqueHorario(
                    dia=dia,
                    horario=horario,
                    tipo='ida',
                    demanda=0,
                    usuarios=[],
                    usuarios_flexibles=[],
                    conductores_disponibles=[]
                )
            
            for horario in HORARIOS_VUELTA:
                self.bloques_vuelta[dia][horario] = BloqueHorario(
                    dia=dia,
                    horario=horario,
                    tipo='vuelta',
                    demanda=0,
                    usuarios=[],
                    usuarios_flexibles=[],
                    conductores_disponibles=[]
                )
        
        # Poblar bloques con datos de usuarios
        for _, row in self.datos.iterrows():
            nombre = row['Nombre']
            
            for dia in DIAS:
                # Procesar IDA
                horario_ida = row.get(f'{dia}_Ida', '')
                if horario_ida and horario_ida in HORARIOS_IDA:
                    bloque = self.bloques_ida[dia][horario_ida]
                    bloque.usuarios.append(nombre)
                    bloque.demanda += 1
                    
                    # Verificar si es flexible
                    if row.get(f'{dia}_Flex_Ida', '') == 'Si':
                        bloque.usuarios_flexibles.append(nombre)
                    
                    # Verificar si es conductor
                    if row.get(f'{dia}_Conductor', '') == 'Si':
                        bloque.conductores_disponibles.append(nombre)
                
                # Procesar VUELTA
                horario_vuelta = row.get(f'{dia}_Vuelta', '')
                if horario_vuelta and horario_vuelta in HORARIOS_VUELTA:
                    bloque = self.bloques_vuelta[dia][horario_vuelta]
                    bloque.usuarios.append(nombre)
                    bloque.demanda += 1
                    
                    # Verificar si es flexible
                    if row.get(f'{dia}_Flex_Vuelta', '') == 'Si':
                        bloque.usuarios_flexibles.append(nombre)
                    
                    # Verificar si es conductor (mismo día)
                    if row.get(f'{dia}_Conductor', '') == 'Si':
                        bloque.conductores_disponibles.append(nombre)
    
    def _calcular_matrices_densidad(self):
        """Calcula las matrices de densidad para visualización"""
        # Matriz de ida: filas = horarios, columnas = días
        self.matriz_densidad_ida = pd.DataFrame(
            index=HORARIOS_IDA,
            columns=DIAS,
            dtype=int
        ).fillna(0)
        
        self.matriz_densidad_vuelta = pd.DataFrame(
            index=HORARIOS_VUELTA,
            columns=DIAS,
            dtype=int
        ).fillna(0)
        
        for dia in DIAS:
            for horario in HORARIOS_IDA:
                self.matriz_densidad_ida.loc[horario, dia] = \
                    self.bloques_ida[dia][horario].demanda
            
            for horario in HORARIOS_VUELTA:
                self.matriz_densidad_vuelta.loc[horario, dia] = \
                    self.bloques_vuelta[dia][horario].demanda
    
    def obtener_bloques_ordenados_por_densidad(self, tipo: str = 'ida') -> List[BloqueHorario]:
        """
        Retorna los bloques ordenados por densidad (mayor a menor).
        
        Args:
            tipo: 'ida' o 'vuelta'
            
        Returns:
            Lista de bloques ordenados por demanda
        """
        bloques = self.bloques_ida if tipo == 'ida' else self.bloques_vuelta
        todos_bloques = []
        
        for dia in DIAS:
            for horario, bloque in bloques[dia].items():
                if bloque.demanda > 0:
                    todos_bloques.append(bloque)
        
        return sorted(todos_bloques, key=lambda x: x.demanda, reverse=True)
    
    def obtener_estadisticas(self) -> Dict:
        """Retorna estadísticas generales del análisis"""
        total_ida = sum(
            self.bloques_ida[d][h].demanda 
            for d in DIAS for h in HORARIOS_IDA
        )
        total_vuelta = sum(
            self.bloques_vuelta[d][h].demanda 
            for d in DIAS for h in HORARIOS_VUELTA
        )
        
        total_conductores_ida = sum(
            len(self.bloques_ida[d][h].conductores_disponibles)
            for d in DIAS for h in HORARIOS_IDA
        )
        total_conductores_vuelta = sum(
            len(self.bloques_vuelta[d][h].conductores_disponibles)
            for d in DIAS for h in HORARIOS_VUELTA
        )
        
        return {
            'total_registros_ida': total_ida,
            'total_registros_vuelta': total_vuelta,
            'total_conductores_ida': total_conductores_ida,
            'total_conductores_vuelta': total_conductores_vuelta,
            'promedio_demanda_ida': total_ida / (len(DIAS) * len(HORARIOS_IDA)) if total_ida > 0 else 0,
            'promedio_demanda_vuelta': total_vuelta / (len(DIAS) * len(HORARIOS_VUELTA)) if total_vuelta > 0 else 0,
            'horario_pico_ida': self._obtener_horario_pico('ida'),
            'horario_pico_vuelta': self._obtener_horario_pico('vuelta'),
        }
    
    def _obtener_horario_pico(self, tipo: str) -> Optional[Tuple[str, str, int]]:
        """Obtiene el horario con mayor demanda"""
        bloques_ordenados = self.obtener_bloques_ordenados_por_densidad(tipo)
        if bloques_ordenados:
            b = bloques_ordenados[0]
            return (b.dia, b.horario, b.demanda)
        return None
    
    def generar_heatmap_data(self) -> Dict:
        """Genera datos para visualización de heatmaps"""
        return {
            'ida': {
                'datos': self.matriz_densidad_ida.values.tolist(),
                'filas': HORARIOS_IDA,
                'columnas': DIAS,
                'max_valor': int(self.matriz_densidad_ida.max().max()) if not self.matriz_densidad_ida.empty else 0
            },
            'vuelta': {
                'datos': self.matriz_densidad_vuelta.values.tolist(),
                'filas': HORARIOS_VUELTA,
                'columnas': DIAS,
                'max_valor': int(self.matriz_densidad_vuelta.max().max()) if not self.matriz_densidad_vuelta.empty else 0
            }
        }


# =============================================================================
# ETAPA 2: ASIGNACIÓN ÓPTIMA DE CONDUCTORES CON PULP
# =============================================================================

class OptimizadorConductores:
    """
    Etapa 2: Optimiza la asignación de conductores usando Programación Lineal.
    Utiliza PuLP para resolver el problema de asignación.
    """
    
    def __init__(self, bloques_ida: Dict, bloques_vuelta: Dict, 
                 capacidad_vehiculo: int = CAPACIDAD_VEHICULO):
        """
        Inicializa el optimizador.
        
        Args:
            bloques_ida: Bloques de horarios de ida del Etapa 1
            bloques_vuelta: Bloques de horarios de vuelta del Etapa 1
            capacidad_vehiculo: Capacidad de cada vehículo
        """
        self.bloques_ida = bloques_ida
        self.bloques_vuelta = bloques_vuelta
        self.capacidad = capacidad_vehiculo
        self.resultados: List[ResultadoOptimizacion] = []
        self.estado_solucion = None
        
    def optimizar(self) -> List[ResultadoOptimizacion]:
        """
        Ejecuta la optimización completa.
        
        Returns:
            Lista de resultados de optimización por bloque
        """
        self.resultados = []
        
        # Optimizar cada día y tipo por separado
        for dia in DIAS:
            # Optimizar IDA
            resultados_ida = self._optimizar_dia(dia, 'ida')
            self.resultados.extend(resultados_ida)
            
            # Optimizar VUELTA
            resultados_vuelta = self._optimizar_dia(dia, 'vuelta')
            self.resultados.extend(resultados_vuelta)
        
        return self.resultados
    
    def _optimizar_dia(self, dia: str, tipo: str) -> List[ResultadoOptimizacion]:
        """
        Optimiza la asignación de conductores para un día específico.
        
        El problema de optimización:
        - Variables: x[conductor, horario] ∈ {0,1} - si el conductor maneja en ese horario
        - Objetivo: Maximizar la cobertura de pasajeros
        - Restricciones:
            * Un conductor puede manejar máximo en un horario por tipo
            * Capacidad del vehículo limitada
            * Solo conductores disponibles pueden ser asignados
        """
        bloques = self.bloques_ida[dia] if tipo == 'ida' else self.bloques_vuelta[dia]
        horarios = HORARIOS_IDA if tipo == 'ida' else HORARIOS_VUELTA
        
        # Recopilar todos los conductores disponibles para este día/tipo
        todos_conductores = set()
        for horario in horarios:
            todos_conductores.update(bloques[horario].conductores_disponibles)
        
        conductores = list(todos_conductores)
        
        # Si no hay conductores, retornar resultados con déficit máximo
        if not conductores:
            return [
                ResultadoOptimizacion(
                    dia=dia,
                    horario=h,
                    tipo=tipo,
                    demanda_total=bloques[h].demanda,
                    conductores_asignados=[],
                    pasajeros_cubiertos=0,
                    deficit=bloques[h].demanda,
                    capacidad_total=0
                )
                for h in horarios if bloques[h].demanda > 0
            ]
        
        # Crear problema de optimización
        problema = LpProblem(f"Asignacion_{dia}_{tipo}", LpMaximize)
        
        # Variables de decisión: x[conductor, horario] = 1 si conductor maneja en horario
        x = LpVariable.dicts(
            "asignacion",
            [(c, h) for c in conductores for h in horarios],
            cat='Binary'
        )
        
        # Variable auxiliar: pasajeros cubiertos por horario
        pasajeros = LpVariable.dicts(
            "pasajeros",
            horarios,
            lowBound=0,
            cat='Integer'
        )
        
        # FUNCIÓN OBJETIVO: Maximizar pasajeros cubiertos
        problema += lpSum([pasajeros[h] for h in horarios]), "Maximizar_Cobertura"
        
        # RESTRICCIÓN 1: Cada conductor puede manejar en máximo un horario
        for c in conductores:
            problema += (
                lpSum([x[(c, h)] for h in horarios]) <= 1,
                f"Max_Un_Horario_{c}"
            )
        
        # RESTRICCIÓN 2: Un conductor solo puede ser asignado donde está disponible
        for c in conductores:
            for h in horarios:
                if c not in bloques[h].conductores_disponibles:
                    problema += (
                        x[(c, h)] == 0,
                        f"Disponibilidad_{c}_{h}"
                    )
        
        # RESTRICCIÓN 3: Pasajeros cubiertos <= capacidad * conductores asignados
        for h in horarios:
            problema += (
                pasajeros[h] <= self.capacidad * lpSum([x[(c, h)] for c in conductores]),
                f"Capacidad_{h}"
            )
        
        # RESTRICCIÓN 4: Pasajeros cubiertos <= demanda real
        for h in horarios:
            demanda = bloques[h].demanda
            problema += (
                pasajeros[h] <= demanda,
                f"Demanda_{h}"
            )
        
        # Resolver el problema
        problema.solve(PULP_CBC_CMD(msg=0))  # msg=0 para silenciar output
        self.estado_solucion = LpStatus[problema.status]
        
        # Procesar resultados
        resultados = []
        for h in horarios:
            if bloques[h].demanda > 0:
                conductores_asignados = [
                    c for c in conductores 
                    if value(x[(c, h)]) == 1
                ]
                
                capacidad_total = len(conductores_asignados) * self.capacidad
                pasajeros_cubiertos = min(int(value(pasajeros[h])), bloques[h].demanda)
                
                resultados.append(ResultadoOptimizacion(
                    dia=dia,
                    horario=h,
                    tipo=tipo,
                    demanda_total=bloques[h].demanda,
                    conductores_asignados=conductores_asignados,
                    pasajeros_cubiertos=pasajeros_cubiertos,
                    deficit=max(0, bloques[h].demanda - capacidad_total),
                    capacidad_total=capacidad_total
                ))
        
        return resultados
    
    def obtener_resumen(self) -> Dict:
        """Genera un resumen de la optimización"""
        if not self.resultados:
            return {}
        
        total_demanda = sum(r.demanda_total for r in self.resultados)
        total_cubiertos = sum(r.pasajeros_cubiertos for r in self.resultados)
        total_deficit = sum(r.deficit for r in self.resultados)
        total_conductores = len(set(
            c for r in self.resultados for c in r.conductores_asignados
        ))
        
        # Agrupar por día
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
        
        return {
            'estado_solucion': self.estado_solucion,
            'total_demanda': total_demanda,
            'total_cubiertos': total_cubiertos,
            'total_deficit': total_deficit,
            'total_conductores_asignados': total_conductores,
            'cobertura_global_pct': round(total_cubiertos / total_demanda * 100, 1) if total_demanda > 0 else 0,
            'por_dia': resumen_dias
        }
    
    def obtener_grid_resultados(self) -> Dict:
        """
        Genera una estructura de grid para visualización.
        Organizado por día -> tipo -> horario
        """
        grid = {}
        
        for dia in DIAS:
            grid[dia] = {'ida': {}, 'vuelta': {}}
        
        for r in self.resultados:
            grid[r.dia][r.tipo][r.horario] = {
                'demanda': r.demanda_total,
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
    
    if datos.empty:
        return {'error': 'No hay datos para optimizar', 'exito': False}
    
    # ETAPA 1: Análisis de Densidad
    analizador = AnalizadorDensidad(datos)
    bloques_ida, bloques_vuelta = analizador.analizar()
    
    estadisticas = analizador.obtener_estadisticas()
    heatmap_data = analizador.generar_heatmap_data()
    bloques_densos_ida = analizador.obtener_bloques_ordenados_por_densidad('ida')
    bloques_densos_vuelta = analizador.obtener_bloques_ordenados_por_densidad('vuelta')
    
    # ETAPA 2: Optimización de Conductores
    optimizador = OptimizadorConductores(bloques_ida, bloques_vuelta, capacidad)
    resultados = optimizador.optimizar()
    
    resumen = optimizador.obtener_resumen()
    grid_resultados = optimizador.obtener_grid_resultados()
    
    return {
        'exito': True,
        'total_usuarios': len(datos),
        
        # Resultados Etapa 1
        'densidad': {
            'estadisticas': estadisticas,
            'heatmap_data': heatmap_data,
            'bloques_densos_ida': [
                {'dia': b.dia, 'horario': b.horario, 'demanda': b.demanda, 
                 'conductores': len(b.conductores_disponibles)}
                for b in bloques_densos_ida[:5]  # Top 5
            ],
            'bloques_densos_vuelta': [
                {'dia': b.dia, 'horario': b.horario, 'demanda': b.demanda,
                 'conductores': len(b.conductores_disponibles)}
                for b in bloques_densos_vuelta[:5]  # Top 5
            ]
        },
        
        # Resultados Etapa 2
        'conductores': {
            'resumen': resumen,
            'grid_resultados': grid_resultados,
            'detalles': [
                {
                    'dia': r.dia,
                    'horario': r.horario,
                    'tipo': r.tipo,
                    'demanda': r.demanda_total,
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
    import json
    
    print("=" * 60)
    print("SISTEMA DE OPTIMIZACIÓN DE TRANSPORTE UNIVERSITARIO")
    print("=" * 60)
    
    resultado = ejecutar_optimizacion('datos_usuarios.csv')
    
    if resultado.get('exito'):
        print(f"\n✓ Optimización completada para {resultado['total_usuarios']} usuarios")
        print("\n--- ETAPA 1: ANÁLISIS DE DENSIDAD ---")
        stats = resultado['densidad']['estadisticas']
        print(f"  Registros totales (ida): {stats['total_registros_ida']}")
        print(f"  Registros totales (vuelta): {stats['total_registros_vuelta']}")
        print(f"  Conductores disponibles (ida): {stats['total_conductores_ida']}")
        print(f"  Conductores disponibles (vuelta): {stats['total_conductores_vuelta']}")
        
        print("\n--- ETAPA 2: ASIGNACIÓN DE CONDUCTORES ---")
        resumen = resultado['conductores']['resumen']
        print(f"  Estado solución: {resumen.get('estado_solucion', 'N/A')}")
        print(f"  Demanda total: {resumen.get('total_demanda', 0)}")
        print(f"  Pasajeros cubiertos: {resumen.get('total_cubiertos', 0)}")
        print(f"  Déficit: {resumen.get('total_deficit', 0)}")
        print(f"  Cobertura: {resumen.get('cobertura_global_pct', 0)}%")
    else:
        print(f"\n✗ Error: {resultado.get('error')}")
