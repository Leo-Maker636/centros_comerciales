"""
busqueda_rucs
Módulo para scraping y procesamiento de información de centros comerciales.

Estructura realizada:

busqueda_rucs/
├── pyproject.toml
├── README.toml
└── src/
    busqueda_rucs/
    ├── __init__.py
    ├── cli.py
    └── procesar.py

"""

# Puedes exponer funciones o clases principales para importaciones
# desde outside code si quieres:
# from .procesar import encontrar_info_cc
from .procesar import encontrar_locales
