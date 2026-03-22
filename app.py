from flask import Flask, render_template, request, redirect, url_for, jsonify
import csv
import os
from datetime import datetime
from optimizador import ejecutar_optimizacion, CAPACIDAD_VEHICULO, HORARIOS_IDA, HORARIOS_VUELTA

app = Flask(__name__)

# Configuración
DATA_FILE = 'datos_usuarios.csv'
COMPENSADORES_BLOQUEADOS_VOLUNTARIO = {'Eduardo R', 'Pablo L'}
HEADERS = [
    'Nombre', 'Timestamp',
    'Lunes_Ida', 'Lunes_Vuelta', 'Lunes_Conductor', 'Lunes_Flex_Ida', 'Lunes_Flex_Vuelta',
    'Martes_Ida', 'Martes_Vuelta', 'Martes_Conductor', 'Martes_Flex_Ida', 'Martes_Flex_Vuelta',
    'Miercoles_Ida', 'Miercoles_Vuelta', 'Miercoles_Conductor', 'Miercoles_Flex_Ida', 'Miercoles_Flex_Vuelta',
    'Jueves_Ida', 'Jueves_Vuelta', 'Jueves_Conductor', 'Jueves_Flex_Ida', 'Jueves_Flex_Vuelta',
    'Voluntario_Segundo_Viaje'
]
DIAS_FORM = ['lunes', 'martes', 'miercoles', 'jueves']
DIAS_TITULO = ['Lunes', 'Martes', 'Miercoles', 'Jueves']


def leer_datos_csv():
    """Leer todos los registros del CSV en memoria"""
    if not os.path.exists(DATA_FILE):
        return []

    # utf-8-sig handles files with or without BOM, avoiding '\ufeffNombre' as header.
    with open(DATA_FILE, 'r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        return list(reader)


def guardar_datos_csv(datos):
    """Sobrescribe el CSV con la lista de registros proporcionada"""
    with open(DATA_FILE, 'w', newline='', encoding='utf-8') as file:
        # Ignora columnas heredadas de versiones anteriores.
        writer = csv.DictWriter(file, fieldnames=HEADERS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(datos)


def construir_fila_desde_form(formulario):
    """Construye y valida una fila del CSV desde los datos del formulario"""
    nombre = formulario.get('nombre', '').strip()
    if not nombre:
        return None, "Error: El nombre es requerido"

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fila_datos = [nombre, timestamp]

    for dia in DIAS_FORM:
        ida = formulario.get(f'{dia}_ida', '')
        vuelta = formulario.get(f'{dia}_vuelta', '')
        conductor = 'Si' if formulario.get(f'{dia}_conductor') else 'No'
        flex_ida = 'Si' if formulario.get(f'{dia}_flex_ida') else 'No'
        flex_vuelta = 'Si' if formulario.get(f'{dia}_flex_vuelta') else 'No'

        fila_datos.extend([ida, vuelta, conductor, flex_ida, flex_vuelta])

    voluntario = 'Si' if formulario.get('voluntario_segundo_viaje') else 'No'
    if nombre in COMPENSADORES_BLOQUEADOS_VOLUNTARIO:
        voluntario = 'No'
    fila_datos.append(voluntario)

    for i, dia in enumerate(DIAS_FORM):
        if fila_datos[2 + i * 5 + 2] == 'Si':
            ida_val = fila_datos[2 + i * 5]
            vuelta_val = fila_datos[2 + i * 5 + 1]
            if not ida_val or not vuelta_val:
                return None, (
                    f"Error: Si estás dispuesto a manejar el {dia.capitalize()}, "
                    "debes seleccionar una hora de ida y vuelta para ese día"
                )

    return fila_datos, None


def fila_a_dict(fila_datos):
    """Convierte una fila en lista al formato dict de DictWriter"""
    return {header: fila_datos[idx] for idx, header in enumerate(HEADERS)}

def inicializar_csv():
    """Crear archivo CSV si no existe"""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(HEADERS)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_data():
    try:
        inicializar_csv()

        fila_datos, error = construir_fila_desde_form(request.form)
        if error:
            return error, 400

        with open(DATA_FILE, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(fila_datos)
        
        return redirect(url_for('success'))
        
    except Exception as e:
        return f"Error al procesar los datos: {str(e)}", 500

@app.route('/success')
def success():
    return """
    <html>
    <head>
        <title>Datos Enviados</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
            .success { color: green; font-size: 24px; margin-bottom: 20px; }
            .link { margin: 10px; }
            a { color: #007bff; text-decoration: none; font-size: 18px; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="success">✓ Datos enviados exitosamente</div>
        <div class="link"><a href="/">Volver al formulario</a></div>
        <div class="link"><a href="/admin">Ver panel de administración</a></div>
    </body>
    </html>
    """

@app.route('/admin')
def admin_panel():
    """Panel de administración para ver datos y ejecutar optimización"""
    try:
        datos = leer_datos_csv()
        return render_template('admin.html', datos=datos, total_usuarios=len(datos))
    except Exception as e:
        return f"Error al cargar datos: {str(e)}", 500


@app.route('/admin/editar/<int:indice>', methods=['GET', 'POST'])
def admin_editar_usuario(indice):
    """Permite editar horarios/preferencias de un registro desde admin"""
    try:
        inicializar_csv()
        datos = leer_datos_csv()

        if indice < 0 or indice >= len(datos):
            return "Registro no encontrado", 404

        if request.method == 'POST':
            fila_datos, error = construir_fila_desde_form(request.form)
            if error:
                return error, 400

            datos[indice] = fila_a_dict(fila_datos)
            guardar_datos_csv(datos)
            return redirect(url_for('admin_panel'))

        usuario = datos[indice]
        return render_template(
            'admin_editar.html',
            usuario=usuario,
            indice=indice,
            dias=[
                {'id': 'lunes', 'label': 'Lunes'},
                {'id': 'martes', 'label': 'Martes'},
                {'id': 'miercoles', 'label': 'Miercoles'},
                {'id': 'jueves', 'label': 'Jueves'},
            ],
            dias_titulo=DIAS_TITULO,
            horarios_ida=HORARIOS_IDA,
            horarios_vuelta=HORARIOS_VUELTA,
            bloqueado_voluntario=usuario.get('Nombre', '') in COMPENSADORES_BLOQUEADOS_VOLUNTARIO
        )
    except Exception as e:
        return f"Error al editar registro: {str(e)}", 500


@app.route('/admin/eliminar/<int:indice>', methods=['POST'])
def admin_eliminar_usuario(indice):
    """Elimina un registro de usuario por índice desde admin"""
    try:
        inicializar_csv()
        datos = leer_datos_csv()

        if indice < 0 or indice >= len(datos):
            return "Registro no encontrado", 404

        datos.pop(indice)
        guardar_datos_csv(datos)
        return redirect(url_for('admin_panel'))
    except Exception as e:
        return f"Error al eliminar registro: {str(e)}", 500

@app.route('/download-csv')
def download_csv():
    """Descargar archivo CSV"""
    try:
        if not os.path.exists(DATA_FILE):
            return "No hay datos para descargar", 404
        
        from flask import send_file
        return send_file(DATA_FILE, as_attachment=True, download_name=f'datos_usuarios_{datetime.now().strftime("%Y%m%d_%H%M")}.csv')
    except Exception as e:
        return f"Error al descargar archivo: {str(e)}", 500


# =============================================================================
# RUTAS DE OPTIMIZACIÓN
# =============================================================================

@app.route('/optimizar')
def optimizar():
    """Ejecuta la optimización y muestra los resultados"""
    try:
        # Verificar que existen datos
        if not os.path.exists(DATA_FILE):
            return render_template('resultados.html', 
                                   error="No hay datos para optimizar. Primero registra algunos usuarios.",
                                   exito=False)
        
        # Obtener capacidad personalizada si se proporciona
        capacidad = request.args.get('capacidad', CAPACIDAD_VEHICULO, type=int)
        
        # Ejecutar optimización
        resultado = ejecutar_optimizacion(DATA_FILE, capacidad)
        
        if not resultado.get('exito'):
            return render_template('resultados.html', 
                                   error=resultado.get('error', 'Error desconocido'),
                                   exito=False)
        
        return render_template('resultados.html',
                               exito=True,
                               total_usuarios=resultado['total_usuarios'],
                               densidad=resultado['densidad'],
                               conductores=resultado['conductores'],
                               capacidad=capacidad)
    
    except Exception as e:
        return render_template('resultados.html', 
                               error=f"Error al ejecutar optimización: {str(e)}",
                               exito=False)


@app.route('/api/optimizar')
def api_optimizar():
    """API JSON para obtener resultados de optimización"""
    try:
        if not os.path.exists(DATA_FILE):
            return jsonify({'exito': False, 'error': 'No hay datos para optimizar'}), 404
        
        capacidad = request.args.get('capacidad', CAPACIDAD_VEHICULO, type=int)
        resultado = ejecutar_optimizacion(DATA_FILE, capacidad)
        
        return jsonify(resultado)
    
    except Exception as e:
        return jsonify({'exito': False, 'error': str(e)}), 500


@app.route('/api/estadisticas')
def api_estadisticas():
    """API para obtener estadísticas rápidas sin optimización completa"""
    try:
        if not os.path.exists(DATA_FILE):
            return jsonify({'exito': False, 'error': 'No hay datos'}), 404
        
        import pandas as pd
        datos = pd.read_csv(DATA_FILE, encoding='utf-8')
        
        if datos.empty:
            return jsonify({'exito': False, 'error': 'No hay registros'}), 404
        
        # Estadísticas básicas
        total_usuarios = len(datos)
        conductores_totales = sum(
            (datos[f'{dia}_Conductor'] == 'Si').sum()
            for dia in DIAS_TITULO
        )
        
        return jsonify({
            'exito': True,
            'total_usuarios': total_usuarios,
            'conductores_totales': int(conductores_totales),
            'ultima_actualizacion': datos['Timestamp'].max() if 'Timestamp' in datos.columns else None
        })
    
    except Exception as e:
        return jsonify({'exito': False, 'error': str(e)}), 500


if __name__ == '__main__':
    inicializar_csv()
    app.run(debug=True, host='0.0.0.0', port=5000)
