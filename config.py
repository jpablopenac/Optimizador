# Configuración para producción en Render

import os

class Config:
    # Configuraciones básicas
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    
    # Configuración de archivos
    DATA_FILE = os.environ.get('DATA_FILE') or 'datos_usuarios.csv'
    
    # Configuraciones de Flask
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    
    # Puerto para Render
    PORT = int(os.environ.get('PORT', 5000))
