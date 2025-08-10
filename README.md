# Recopilador de Datos de Turnos Universitarios

Una aplicación web Flask para recopilar y almacenar preferencias de usuarios para turnos de transporte universitario.

## Características

- **Formulario web intuitivo** para capturar preferencias de usuarios
- **Validación automática** de datos y restricciones
- **Panel de administración** para visualización de datos recopilados
- **Almacenamiento persistente** en CSV
- **Estadísticas en tiempo real** de los datos recopilados
- **Responsive design** para dispositivos móviles

## Requisitos del Sistema

- Python 3.8+
- Flask 2.3.3+
- pandas (para manejo de datos)

## Instalación

1. **Clonar o descargar** el proyecto
2. **Crear entorno virtual**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # o
   source .venv/bin/activate  # Linux/Mac
   ```
3. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

## Ejecución

1. **Ejecutar la aplicación**:
   ```bash
   python app.py
   ```
2. **Abrir navegador** en `http://localhost:5000`

## Uso

### Para Usuarios
1. Ir a la página principal
2. Llenar el formulario con:
   - Nombre
   - Preferencias de horarios (ida y vuelta)
   - Flexibilidad por día
   - Disponibilidad para conducir
   - Voluntario para segundo viaje
3. Enviar formulario

### Para Administradores
1. Ir a `/admin`
2. Ver estadísticas y datos de usuarios recopilados
3. Descargar datos en CSV para análisis posterior

## Estructura del Proyecto

```
Optimizador/
├── app.py                 # Aplicación Flask principal
├── requirements.txt       # Dependencias
├── datos_usuarios.csv     # Datos persistentes (generado automáticamente)
└── templates/
    ├── index.html         # Formulario principal
    └── admin.html         # Panel de administración
```

## Datos Recopilados

La aplicación recopila la siguiente información de cada usuario:
- **Información personal**: Nombre y timestamp
- **Preferencias de horarios**: Ida y vuelta para cada día de la semana
- **Flexibilidad**: Disponibilidad para cambiar horarios si es necesario
- **Disponibilidad para conducir**: Por día de la semana
- **Voluntario para segundo viaje**: Disponibilidad para viajes adicionales

## Estadísticas Disponibles

El panel de administración muestra:
- Total de usuarios registrados
- Total de viajes solicitados
- Número de conductores disponibles
- Cantidad de voluntarios para segundo viaje

## Despliegue

### PythonAnywhere (Recomendado - Gratuito)
1. Subir archivos al servidor
2. Configurar aplicación Flask
3. Instalar dependencias
4. El archivo CSV se mantendrá persistente

### Otras Plataformas
- Heroku (con plan gratuito limitado)
- Railway
- Render
- DigitalOcean App Platform

## Configuración

### Variables principales en `app.py`:
- `DATA_FILE`: Nombre del archivo CSV de datos
- `HEADERS`: Columnas del CSV
- `host` y `port`: Configuración del servidor

### Capacidad de almacenamiento:
Los datos se almacenan en formato CSV con todas las preferencias de usuarios, permitiendo análisis posterior con herramientas externas.

## Validaciones Implementadas

1. **Nombre requerido**
2. **Conductor debe tener ida y vuelta** el mismo día
3. **Solo una hora por día** (ida/vuelta)
4. **Flexibilidad solo en turnos adyacentes**
5. **Segundo viaje solo si es voluntario**

## API Endpoints

- `GET /` - Formulario principal
- `POST /submit` - Enviar datos de usuario
- `GET /success` - Confirmación de envío
- `GET /admin` - Panel de administración
- `GET /download-csv` - Descargar datos

## Solución de Problemas

### Puerto ocupado
Cambiar puerto en `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=8000)
```

### Problemas con CSV
Si el archivo CSV se corrompe, simplemente eliminarlo. La aplicación creará uno nuevo automáticamente.

## Contribuir

1. Fork del repositorio
2. Crear rama de feature
3. Hacer commits descriptivos
4. Enviar pull request

## Licencia

MIT License - Ver archivo LICENSE para detalles.
