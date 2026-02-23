"""
transformar_fact
Módulo para transformacion de datos de facturación.

Estructura realizada:

transformar_fact/
├── pyproject.toml
├── README.toml
└── src/
    transformar_fact/
    ├── __init__.py
    ├── cli.py
    ├── traer_datos.py
    ├── transformar_fact.py
    └── procesar.py

"""

# Puedes exponer funciones o clases principales para importaciones
# desde outside code si quieres:
# from .procesar import encontrar_info_cc
from .traer_datos import leer_y_guardar_datos_mysql
from .transformar_datos import transformacion_backups
