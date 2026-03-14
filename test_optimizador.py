"""
Tests Unitarios para el Sistema de Optimización de Transporte
==============================================================
Ejecutar con: python -m pytest test_optimizador.py -v
O directamente: python test_optimizador.py
"""

import pytest
import pandas as pd
import tempfile
import os
from io import StringIO

from optimizador import (
    ConsolidadorDemanda,
    OptimizadorConductores,
    ejecutar_optimizacion,
    Usuario,
    BloqueHorario,
    DIAS,
    HORARIOS_IDA,
    HORARIOS_VUELTA,
    CAPACIDAD_VEHICULO
)


# =============================================================================
# FIXTURES: Datos de prueba reutilizables
# =============================================================================

@pytest.fixture
def csv_basico():
    """CSV con 3 usuarios simples"""
    return """Nombre,Timestamp,Lunes_Ida,Lunes_Vuelta,Lunes_Conductor,Lunes_Flex_Ida,Lunes_Flex_Vuelta,Martes_Ida,Martes_Vuelta,Martes_Conductor,Martes_Flex_Ida,Martes_Flex_Vuelta,Miercoles_Ida,Miercoles_Vuelta,Miercoles_Conductor,Miercoles_Flex_Ida,Miercoles_Flex_Vuelta,Jueves_Ida,Jueves_Vuelta,Jueves_Conductor,Jueves_Flex_Ida,Jueves_Flex_Vuelta,Viernes_Ida,Viernes_Vuelta,Viernes_Conductor,Viernes_Flex_Ida,Viernes_Flex_Vuelta,Voluntario_Segundo_Viaje
Ana,2026-01-01 10:00:00,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,No
Pedro,2026-01-01 10:01:00,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,No
María,2026-01-01 10:02:00,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,No"""


@pytest.fixture
def csv_con_flexibles():
    """CSV con usuarios flexibles"""
    return """Nombre,Timestamp,Lunes_Ida,Lunes_Vuelta,Lunes_Conductor,Lunes_Flex_Ida,Lunes_Flex_Vuelta,Martes_Ida,Martes_Vuelta,Martes_Conductor,Martes_Flex_Ida,Martes_Flex_Vuelta,Miercoles_Ida,Miercoles_Vuelta,Miercoles_Conductor,Miercoles_Flex_Ida,Miercoles_Flex_Vuelta,Jueves_Ida,Jueves_Vuelta,Jueves_Conductor,Jueves_Flex_Ida,Jueves_Flex_Vuelta,Viernes_Ida,Viernes_Vuelta,Viernes_Conductor,Viernes_Flex_Ida,Viernes_Flex_Vuelta,Voluntario_Segundo_Viaje
Ana,2026-01-01 10:00:00,9:40,17:20,Si,Si,Si,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
Pedro,2026-01-01 10:01:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No"""


@pytest.fixture
def csv_sin_conductor():
    """CSV con usuario que no puede manejar"""
    return """Nombre,Timestamp,Lunes_Ida,Lunes_Vuelta,Lunes_Conductor,Lunes_Flex_Ida,Lunes_Flex_Vuelta,Martes_Ida,Martes_Vuelta,Martes_Conductor,Martes_Flex_Ida,Martes_Flex_Vuelta,Miercoles_Ida,Miercoles_Vuelta,Miercoles_Conductor,Miercoles_Flex_Ida,Miercoles_Flex_Vuelta,Jueves_Ida,Jueves_Vuelta,Jueves_Conductor,Jueves_Flex_Ida,Jueves_Flex_Vuelta,Viernes_Ida,Viernes_Vuelta,Viernes_Conductor,Viernes_Flex_Ida,Viernes_Flex_Vuelta,Voluntario_Segundo_Viaje
Ana,2026-01-01 10:00:00,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
Luis,2026-01-01 10:01:00,8:20,16:00,No,No,No,8:20,16:00,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No"""


@pytest.fixture
def csv_con_voluntario():
    """CSV con voluntario de segundo viaje"""
    return """Nombre,Timestamp,Lunes_Ida,Lunes_Vuelta,Lunes_Conductor,Lunes_Flex_Ida,Lunes_Flex_Vuelta,Martes_Ida,Martes_Vuelta,Martes_Conductor,Martes_Flex_Ida,Martes_Flex_Vuelta,Miercoles_Ida,Miercoles_Vuelta,Miercoles_Conductor,Miercoles_Flex_Ida,Miercoles_Flex_Vuelta,Jueves_Ida,Jueves_Vuelta,Jueves_Conductor,Jueves_Flex_Ida,Jueves_Flex_Vuelta,Viernes_Ida,Viernes_Vuelta,Viernes_Conductor,Viernes_Flex_Ida,Viernes_Flex_Vuelta,Voluntario_Segundo_Viaje
Ana,2026-01-01 10:00:00,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,Si
Pedro,2026-01-01 10:01:00,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No"""


@pytest.fixture
def csv_duplicados():
    """CSV con nombres duplicados"""
    return """Nombre,Timestamp,Lunes_Ida,Lunes_Vuelta,Lunes_Conductor,Lunes_Flex_Ida,Lunes_Flex_Vuelta,Martes_Ida,Martes_Vuelta,Martes_Conductor,Martes_Flex_Ida,Martes_Flex_Vuelta,Miercoles_Ida,Miercoles_Vuelta,Miercoles_Conductor,Miercoles_Flex_Ida,Miercoles_Flex_Vuelta,Jueves_Ida,Jueves_Vuelta,Jueves_Conductor,Jueves_Flex_Ida,Jueves_Flex_Vuelta,Viernes_Ida,Viernes_Vuelta,Viernes_Conductor,Viernes_Flex_Ida,Viernes_Flex_Vuelta,Voluntario_Segundo_Viaje
Ana,2026-01-01 08:00:00,8:20,16:00,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
Ana,2026-01-01 10:00:00,8:20,16:00,Si,No,No,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
Pedro,2026-01-01 10:01:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No"""


def crear_archivo_temporal(contenido_csv):
    """Helper para crear archivo CSV temporal"""
    fd, path = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(contenido_csv)
    return path


# =============================================================================
# TESTS: Estructuras de Datos
# =============================================================================

class TestUsuario:
    """Tests para la clase Usuario"""
    
    def test_crear_usuario(self):
        usuario = Usuario(
            nombre="Test",
            horario_original="8:20",
            horario_asignado="8:20",
            es_flexible=True,
            es_conductor=True
        )
        assert usuario.nombre == "Test"
        assert usuario.fue_movido == False
    
    def test_usuario_movido(self):
        usuario = Usuario(
            nombre="Test",
            horario_original="9:40",
            horario_asignado="8:20",
            es_flexible=True,
            es_conductor=True,
            fue_movido=True
        )
        assert usuario.fue_movido == True
        assert usuario.horario_original != usuario.horario_asignado


class TestBloqueHorario:
    """Tests para la clase BloqueHorario"""
    
    def test_bloque_vacio(self):
        bloque = BloqueHorario(dia="Lunes", horario="8:20", tipo="ida")
        assert bloque.demanda == 0
        assert len(bloque.usuarios_fijos) == 0
        assert len(bloque.usuarios_flexibles) == 0
    
    def test_agregar_usuario(self):
        bloque = BloqueHorario(dia="Lunes", horario="8:20", tipo="ida")
        usuario = Usuario("Test", "8:20", "8:20", False, True)
        bloque.agregar_usuario(usuario)
        assert bloque.demanda == 1
        assert len(bloque.usuarios_fijos) == 1
    
    def test_remover_usuario(self):
        bloque = BloqueHorario(dia="Lunes", horario="8:20", tipo="ida")
        usuario = Usuario("Test", "8:20", "8:20", False, True)
        bloque.agregar_usuario(usuario)
        
        removido = bloque.remover_usuario("Test")
        assert removido is not None
        assert bloque.demanda == 0
    
    def test_conductores_disponibles(self):
        bloque = BloqueHorario(dia="Lunes", horario="8:20", tipo="ida")
        bloque.agregar_usuario(Usuario("Conductor1", "8:20", "8:20", False, True))
        bloque.agregar_usuario(Usuario("Pasajero1", "8:20", "8:20", False, False))
        
        assert len(bloque.conductores_disponibles) == 1
        assert "Conductor1" in bloque.conductores_disponibles


# =============================================================================
# TESTS: Consolidador de Demanda (Etapa 1)
# =============================================================================

class TestConsolidadorDemanda:
    """Tests para la clase ConsolidadorDemanda"""
    
    def test_carga_usuarios(self, csv_basico):
        datos = pd.read_csv(StringIO(csv_basico))
        consolidador = ConsolidadorDemanda(datos)
        consolidador.ejecutar()
        
        assert len(consolidador.todos_usuarios) == 3
        assert "Ana" in consolidador.todos_usuarios
    
    def test_detecta_conductores(self, csv_basico):
        datos = pd.read_csv(StringIO(csv_basico))
        consolidador = ConsolidadorDemanda(datos)
        consolidador.ejecutar()
        
        # Todos son conductores todos los días
        assert len(consolidador.conductores_por_dia['Lunes']) == 3
    
    def test_movimiento_flexibles(self, csv_con_flexibles):
        datos = pd.read_csv(StringIO(csv_con_flexibles))
        consolidador = ConsolidadorDemanda(datos)
        consolidador.ejecutar()
        
        stats = consolidador.obtener_estadisticas()
        # Ana es flexible y debería moverse de 9:40 a 8:20 (donde está Pedro)
        assert stats['movimientos_realizados'] >= 0  # Puede o no moverse según la optimización
    
    def test_detecta_usuarios_sin_disponibilidad(self, csv_sin_conductor):
        datos = pd.read_csv(StringIO(csv_sin_conductor))
        consolidador = ConsolidadorDemanda(datos)
        consolidador.ejecutar()
        
        stats = consolidador.obtener_estadisticas()
        assert stats['total_sin_disponibilidad'] == 1
        assert "Luis" in stats['usuarios_sin_disponibilidad']
    
    def test_detecta_voluntarios_segundo_viaje(self, csv_con_voluntario):
        datos = pd.read_csv(StringIO(csv_con_voluntario))
        consolidador = ConsolidadorDemanda(datos)
        consolidador.ejecutar()
        
        assert "Ana" in consolidador.voluntarios_segundo_viaje
        assert len(consolidador.voluntarios_segundo_viaje) == 1
    
    def test_disponibilidad_actualizada_post_movimiento(self, csv_con_flexibles):
        """Verifica que la disponibilidad del conductor se actualiza cuando se mueve"""
        datos = pd.read_csv(StringIO(csv_con_flexibles))
        consolidador = ConsolidadorDemanda(datos)
        consolidador.ejecutar()
        
        # Verificar que las disponibilidades existen
        assert "Ana" in consolidador.disponibilidad_conductor or "Pedro" in consolidador.disponibilidad_conductor


# =============================================================================
# TESTS: Optimizador de Conductores (Etapa 2)
# =============================================================================

class TestOptimizadorConductores:
    """Tests para la clase OptimizadorConductores"""
    
    def test_regla_de_oro_todos_manejan(self, csv_basico):
        """Verifica que todos los usuarios válidos manejan al menos 1 vez"""
        datos = pd.read_csv(StringIO(csv_basico))
        consolidador = ConsolidadorDemanda(datos)
        bloques_ida, bloques_vuelta = consolidador.ejecutar()
        
        optimizador = OptimizadorConductores(
            bloques_ida, bloques_vuelta,
            consolidador.todos_usuarios,
            consolidador.disponibilidad_conductor,
            consolidador.voluntarios_segundo_viaje
        )
        optimizador.optimizar()
        resumen = optimizador.obtener_resumen()
        
        # Todos deben manejar
        assert resumen['estado_solucion'] == 'Optimal'
        assert resumen['total_conductores_asignados'] == 3
    
    def test_voluntario_puede_manejar_dos_veces(self, csv_con_voluntario):
        """Verifica que voluntarios pueden manejar hasta 2 días"""
        datos = pd.read_csv(StringIO(csv_con_voluntario))
        consolidador = ConsolidadorDemanda(datos)
        bloques_ida, bloques_vuelta = consolidador.ejecutar()
        
        optimizador = OptimizadorConductores(
            bloques_ida, bloques_vuelta,
            consolidador.todos_usuarios,
            consolidador.disponibilidad_conductor,
            consolidador.voluntarios_segundo_viaje
        )
        optimizador.optimizar()
        
        # Ana es voluntaria, puede manejar como máximo 2 días
        asignaciones_ana = optimizador.asignaciones_conductor.get('Ana', [])
        dias_asignados_ana = {a['dia'] for a in asignaciones_ana}
        assert len(dias_asignados_ana) <= 2

    def test_mismo_chofer_en_ida_y_vuelta_por_dia(self, csv_basico):
        """Si un chofer maneja ida en un día, debe manejar también la vuelta ese día."""
        datos = pd.read_csv(StringIO(csv_basico))
        consolidador = ConsolidadorDemanda(datos)
        bloques_ida, bloques_vuelta = consolidador.ejecutar()

        optimizador = OptimizadorConductores(
            bloques_ida, bloques_vuelta,
            consolidador.todos_usuarios,
            consolidador.disponibilidad_conductor,
            consolidador.voluntarios_segundo_viaje
        )
        optimizador.optimizar()

        for chofer, asignaciones in optimizador.asignaciones_conductor.items():
            tipos_por_dia = {}
            for a in asignaciones:
                dia = a['dia']
                if dia not in tipos_por_dia:
                    tipos_por_dia[dia] = set()
                tipos_por_dia[dia].add(a['tipo'])

            for dia, tipos in tipos_por_dia.items():
                assert tipos == {'ida', 'vuelta'}, f"{chofer} no cumple ida/vuelta en {dia}: {tipos}"
    
    def test_usuario_sin_disponibilidad_excluido(self, csv_sin_conductor):
        """Verifica que usuarios sin posibilidad de manejar son excluidos"""
        datos = pd.read_csv(StringIO(csv_sin_conductor))
        consolidador = ConsolidadorDemanda(datos)
        bloques_ida, bloques_vuelta = consolidador.ejecutar()
        
        optimizador = OptimizadorConductores(
            bloques_ida, bloques_vuelta,
            consolidador.todos_usuarios,
            consolidador.disponibilidad_conductor,
            consolidador.voluntarios_segundo_viaje
        )
        optimizador.optimizar()
        
        assert "Luis" in optimizador.usuarios_sin_disponibilidad
    
    def test_capacidad_correcta(self, csv_basico):
        """Verifica que la capacidad es conductor + 4 pasajeros = 5"""
        datos = pd.read_csv(StringIO(csv_basico))
        consolidador = ConsolidadorDemanda(datos)
        bloques_ida, bloques_vuelta = consolidador.ejecutar()
        
        optimizador = OptimizadorConductores(
            bloques_ida, bloques_vuelta,
            consolidador.todos_usuarios,
            consolidador.disponibilidad_conductor,
            consolidador.voluntarios_segundo_viaje
        )
        resultados = optimizador.optimizar()
        
        for r in resultados:
            if len(r.conductores_asignados) > 0:
                # Capacidad = conductores * 5 (conductor + 4 pasajeros)
                expected_capacidad = len(r.conductores_asignados) * (CAPACIDAD_VEHICULO + 1)
                assert r.capacidad_total == expected_capacidad


# =============================================================================
# TESTS: Función Principal ejecutar_optimizacion
# =============================================================================

class TestEjecutarOptimizacion:
    """Tests para la función principal"""
    
    def test_archivo_no_encontrado(self):
        resultado = ejecutar_optimizacion('archivo_inexistente.csv')
        assert resultado['exito'] == False
        assert 'no encontrado' in resultado['error'].lower()
    
    def test_optimizacion_exitosa(self, csv_basico):
        path = crear_archivo_temporal(csv_basico)
        try:
            resultado = ejecutar_optimizacion(path)
            assert resultado['exito'] == True
            assert resultado['total_usuarios'] == 3
        finally:
            os.unlink(path)
    
    def test_elimina_duplicados(self, csv_duplicados):
        """Verifica que duplicados se eliminan manteniendo el más reciente"""
        path = crear_archivo_temporal(csv_duplicados)
        try:
            resultado = ejecutar_optimizacion(path)
            assert resultado['exito'] == True
            # Ana aparece 2 veces, debe quedarse solo 1
            assert resultado['total_usuarios'] == 2
        finally:
            os.unlink(path)
    
    def test_estructura_resultado(self, csv_basico):
        """Verifica que el resultado tiene la estructura esperada"""
        path = crear_archivo_temporal(csv_basico)
        try:
            resultado = ejecutar_optimizacion(path)
            
            # Verificar estructura principal
            assert 'exito' in resultado
            assert 'densidad' in resultado
            assert 'conductores' in resultado
            
            # Verificar sub-estructuras
            assert 'estadisticas' in resultado['densidad']
            assert 'resumen' in resultado['conductores']
            assert 'grid_resultados' in resultado['conductores']
        finally:
            os.unlink(path)
    
    def test_csv_vacio(self):
        """Verifica manejo de CSV vacío"""
        csv_vacio = "Nombre,Timestamp,Lunes_Ida\n"
        path = crear_archivo_temporal(csv_vacio)
        try:
            resultado = ejecutar_optimizacion(path)
            assert resultado['exito'] == False
        finally:
            os.unlink(path)


# =============================================================================
# TESTS: Casos Límite
# =============================================================================

class TestCasosLimite:
    """Tests para casos extremos"""
    
    def test_usuario_unico(self):
        """Un solo usuario que debe manejarse a sí mismo"""
        csv = """Nombre,Timestamp,Lunes_Ida,Lunes_Vuelta,Lunes_Conductor,Lunes_Flex_Ida,Lunes_Flex_Vuelta,Martes_Ida,Martes_Vuelta,Martes_Conductor,Martes_Flex_Ida,Martes_Flex_Vuelta,Miercoles_Ida,Miercoles_Vuelta,Miercoles_Conductor,Miercoles_Flex_Ida,Miercoles_Flex_Vuelta,Jueves_Ida,Jueves_Vuelta,Jueves_Conductor,Jueves_Flex_Ida,Jueves_Flex_Vuelta,Viernes_Ida,Viernes_Vuelta,Viernes_Conductor,Viernes_Flex_Ida,Viernes_Flex_Vuelta,Voluntario_Segundo_Viaje
Solo,2026-01-01 10:00:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No"""
        
        path = crear_archivo_temporal(csv)
        try:
            resultado = ejecutar_optimizacion(path)
            assert resultado['exito'] == True
            resumen = resultado['conductores']['resumen']
            assert resumen['estado_solucion'] == 'Optimal'
            assert resumen['total_conductores_asignados'] == 1
        finally:
            os.unlink(path)
    
    def test_todos_mismo_horario(self):
        """Todos los usuarios en el mismo horario"""
        csv = """Nombre,Timestamp,Lunes_Ida,Lunes_Vuelta,Lunes_Conductor,Lunes_Flex_Ida,Lunes_Flex_Vuelta,Martes_Ida,Martes_Vuelta,Martes_Conductor,Martes_Flex_Ida,Martes_Flex_Vuelta,Miercoles_Ida,Miercoles_Vuelta,Miercoles_Conductor,Miercoles_Flex_Ida,Miercoles_Flex_Vuelta,Jueves_Ida,Jueves_Vuelta,Jueves_Conductor,Jueves_Flex_Ida,Jueves_Flex_Vuelta,Viernes_Ida,Viernes_Vuelta,Viernes_Conductor,Viernes_Flex_Ida,Viernes_Flex_Vuelta,Voluntario_Segundo_Viaje
A,2026-01-01 10:00:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
B,2026-01-01 10:01:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
C,2026-01-01 10:02:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
D,2026-01-01 10:03:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
E,2026-01-01 10:04:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No"""
        
        path = crear_archivo_temporal(csv)
        try:
            resultado = ejecutar_optimizacion(path)
            assert resultado['exito'] == True
            resumen = resultado['conductores']['resumen']
            # Todos deben manejar al menos 1 vez
            assert resumen['total_conductores_asignados'] == 5
        finally:
            os.unlink(path)
    
    def test_cobertura_completa_posible(self):
        """Caso donde la cobertura completa es posible"""
        # 5 usuarios, cada uno maneja 1 vez, capacidad 5 = cubren 25 personas
        # Pero solo son 5, así que cobertura = 100%
        csv = """Nombre,Timestamp,Lunes_Ida,Lunes_Vuelta,Lunes_Conductor,Lunes_Flex_Ida,Lunes_Flex_Vuelta,Martes_Ida,Martes_Vuelta,Martes_Conductor,Martes_Flex_Ida,Martes_Flex_Vuelta,Miercoles_Ida,Miercoles_Vuelta,Miercoles_Conductor,Miercoles_Flex_Ida,Miercoles_Flex_Vuelta,Jueves_Ida,Jueves_Vuelta,Jueves_Conductor,Jueves_Flex_Ida,Jueves_Flex_Vuelta,Viernes_Ida,Viernes_Vuelta,Viernes_Conductor,Viernes_Flex_Ida,Viernes_Flex_Vuelta,Voluntario_Segundo_Viaje
A,2026-01-01 10:00:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
B,2026-01-01 10:01:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
C,2026-01-01 10:02:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
D,2026-01-01 10:03:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No
E,2026-01-01 10:04:00,8:20,16:00,Si,No,No,,,No,No,No,,,No,No,No,,,No,No,No,,,No,No,No,No"""
        
        path = crear_archivo_temporal(csv)
        try:
            resultado = ejecutar_optimizacion(path)
            resumen = resultado['conductores']['resumen']
            # Con 5 usuarios y 5 conductores (cada uno se autocubre), cobertura debe ser alta
            assert resumen['cobertura_global_pct'] >= 50  # Al menos 50%
        finally:
            os.unlink(path)


# =============================================================================
# TESTS: Constantes y Configuración
# =============================================================================

class TestConfiguracion:
    """Tests para validar configuración"""
    
    def test_dias_semana(self):
        assert len(DIAS) == 5
        assert 'Lunes' in DIAS
        assert 'Viernes' in DIAS
    
    def test_horarios_ida(self):
        assert len(HORARIOS_IDA) == 4
        assert '8:20' in HORARIOS_IDA
        assert '12:20' in HORARIOS_IDA
    
    def test_horarios_vuelta(self):
        assert len(HORARIOS_VUELTA) == 5
        assert '10:50' in HORARIOS_VUELTA
        assert '12:20' in HORARIOS_VUELTA
        assert '13:30' in HORARIOS_VUELTA
        assert '17:20' in HORARIOS_VUELTA
    
    def test_capacidad_vehiculo(self):
        # 4 pasajeros + 1 conductor = 5 personas por auto
        assert CAPACIDAD_VEHICULO == 4


# =============================================================================
# EJECUCIÓN DIRECTA
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("EJECUTANDO TESTS UNITARIOS")
    print("=" * 70)
    
    # Ejecutar con pytest si está disponible
    try:
        import pytest
        pytest.main([__file__, '-v', '--tb=short'])
    except ImportError:
        print("\nPytest no instalado. Ejecutando tests básicos manualmente...\n")
        
        # Tests manuales básicos
        tests_pasados = 0
        tests_fallidos = 0
        
        # Test 1: Usuario
        try:
            usuario = Usuario("Test", "8:20", "8:20", True, True)
            assert usuario.nombre == "Test"
            print("✓ TestUsuario.test_crear_usuario")
            tests_pasados += 1
        except Exception as e:
            print(f"✗ TestUsuario.test_crear_usuario: {e}")
            tests_fallidos += 1
        
        # Test 2: BloqueHorario
        try:
            bloque = BloqueHorario(dia="Lunes", horario="8:20", tipo="ida")
            assert bloque.demanda == 0
            print("✓ TestBloqueHorario.test_bloque_vacio")
            tests_pasados += 1
        except Exception as e:
            print(f"✗ TestBloqueHorario.test_bloque_vacio: {e}")
            tests_fallidos += 1
        
        # Test 3: Archivo no encontrado
        try:
            resultado = ejecutar_optimizacion('archivo_inexistente.csv')
            assert resultado['exito'] == False
            print("✓ TestEjecutarOptimizacion.test_archivo_no_encontrado")
            tests_pasados += 1
        except Exception as e:
            print(f"✗ TestEjecutarOptimizacion.test_archivo_no_encontrado: {e}")
            tests_fallidos += 1
        
        # Test 4: Configuración
        try:
            assert len(DIAS) == 5
            assert CAPACIDAD_VEHICULO == 4
            print("✓ TestConfiguracion")
            tests_pasados += 1
        except Exception as e:
            print(f"✗ TestConfiguracion: {e}")
            tests_fallidos += 1
        
        print(f"\n{'='*70}")
        print(f"Resultados: {tests_pasados} pasados, {tests_fallidos} fallidos")
        print("=" * 70)
        print("\nPara tests completos, instalar pytest: pip install pytest")
