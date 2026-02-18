from transformar_fact import leer_y_guardar_datos_mysql
from rich.console import Console
from pathlib import Path
import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        description="Búsqueda de RUCs por centros comerciales y descarga de facturas"
    )

    # Argumento opcional verbose
    parser.add_argument(
        "--verbose", action="store_true", help="Activa mensajes detallados"
    )

    # Ruta al archivo de credenciales
    parser.add_argument(
        "--ruta-credenciales-data-fact",
        type=str,
        required=True,
        help="Ruta al archivo de credenciales para conectarse a la base de datos",
    )

    # Lista de RUCs a buscar
    parser.add_argument(
        "--id-establecimientos-a-buscar",
        type=str,
        nargs="+",
        required=True,
        help="Lista de RUCs que se desean consultar",
    )

    return parser.parse_args()


def main():
    console = Console()
    args = parse_args()
    ruta_credenciales_data_fact = Path(args.ruta_credenciales_data_fact)
    id_establecimientos_a_buscar = args.id_establecimientos_a_buscar
    verbose = args.verbose
    with console.status("trayendo las facturas de los lugares especificados") as status:
        leer_y_guardar_datos_mysql(
            id_establecimientos_a_buscar=id_establecimientos_a_buscar,
            ruta_credenciales_data_fact=ruta_credenciales_data_fact,
            param_verbose=verbose,
        )
        status.update("Se termino de traer todos los datos.")


if __name__ == "__main__":
    main()
