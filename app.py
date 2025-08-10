from flask import Flask, render_template, request, redirect, url_for
import csv
import os
from datetime import datetime

app = Flask(__name__)

# Configuración
DATA_FILE = 'datos_usuarios.csv'
HEADERS = [
    'Nombre', 'Timestamp',
    'Lunes_Ida', 'Lunes_Vuelta', 'Lunes_Conductor', 'Lunes_Flex_Ida', 'Lunes_Flex_Vuelta',
    'Martes_Ida', 'Martes_Vuelta', 'Martes_Conductor', 'Martes_Flex_Ida', 'Martes_Flex_Vuelta',
    'Miercoles_Ida', 'Miercoles_Vuelta', 'Miercoles_Conductor', 'Miercoles_Flex_Ida', 'Miercoles_Flex_Vuelta',
    'Jueves_Ida', 'Jueves_Vuelta', 'Jueves_Conductor', 'Jueves_Flex_Ida', 'Jueves_Flex_Vuelta',
    'Viernes_Ida', 'Viernes_Vuelta', 'Viernes_Conductor', 'Viernes_Flex_Ida', 'Viernes_Flex_Vuelta',
    'Voluntario_Segundo_Viaje'
]

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
        # Inicializar CSV si no existe
        inicializar_csv()
        
        # Recopilar datos del formulario
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            return "Error: El nombre es requerido", 400
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Días de la semana
        dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes']
        
        # Preparar fila de datos
        fila_datos = [nombre, timestamp]
        
        # Procesar cada día
        for dia in dias:
            # Ida (radio button - solo una opción)
            ida = request.form.get(f'{dia}_ida', '')
            fila_datos.append(ida)
            
            # Vuelta (radio button - solo una opción)
            vuelta = request.form.get(f'{dia}_vuelta', '')
            fila_datos.append(vuelta)
            
            # Conductor (checkbox)
            conductor = 'Si' if request.form.get(f'{dia}_conductor') else 'No'
            fila_datos.append(conductor)
            
            # Flexibilidad ida (checkbox)
            flex_ida = 'Si' if request.form.get(f'{dia}_flex_ida') else 'No'
            fila_datos.append(flex_ida)
            
            # Flexibilidad vuelta (checkbox)
            flex_vuelta = 'Si' if request.form.get(f'{dia}_flex_vuelta') else 'No'
            fila_datos.append(flex_vuelta)
        
        # Voluntario segundo viaje
        voluntario = 'Si' if request.form.get('voluntario_segundo_viaje') else 'No'
        fila_datos.append(voluntario)
        
        # Validar que si marca conductor, tenga ida y vuelta ese día
        for i, dia in enumerate(dias):
            if fila_datos[2 + i*5 + 2] == 'Si':  # Si es conductor
                ida_val = fila_datos[2 + i*5]     # Ida
                vuelta_val = fila_datos[2 + i*5 + 1]  # Vuelta
                if not ida_val or not vuelta_val:
                    return f"Error: Si estás dispuesto a manejar el {dia.capitalize()}, debes seleccionar una hora de ida y vuelta para ese día", 400
        
        # Escribir al archivo CSV
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
        # Leer datos del CSV
        datos = []
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                datos = list(reader)
        
        return render_template('admin.html', datos=datos, total_usuarios=len(datos))
    except Exception as e:
        return f"Error al cargar datos: {str(e)}", 500

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

if __name__ == '__main__':
    inicializar_csv()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)
