from transformar_datos import leer_y_guardar_datos_mysql
from rich.console import Console
import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        description="Búsqueda de RUCs por centros comerciales"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Activa mensajes detallados"
    )
    parser.add_argument(
        "centros_comerciales",
        type=str,
        nargs="+",
        help="Lista de centros comerciales a procesar",
    )
    return parser.parse_args()


def main():
    console = Console()
    args = parse_args()
    verbose = args.verbose
    with console.status("trayendo las facturas de los lugares especificados") as status:
        leer_y_guardar_datos_mysql(param_verbose=verbose)
        status.update("Se termino de traer todos los datos.")


if __name__ == "__main__":
    main()
