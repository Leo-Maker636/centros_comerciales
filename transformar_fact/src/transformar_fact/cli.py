from transformar_fact import leer_y_guardar_datos_mysql, transformacion_backups
from rich.console import Console
from pathlib import Path
import argparse, sys, polars as pl


def parse_args():
    parser = argparse.ArgumentParser(
        description="Búsqueda de RUCs por centros comerciales y descarga de facturas"
    )

    # Argumento opcional verbose
    parser.add_argument(
        "--verbose", action="store_true", help="Activa mensajes detallados"
    )

    # Argumento opcional verbose
    parser.add_argument(
        "--solo-pivotear",
        action="store_true",
        help="solo pivotea los resultados ya guardados",
    )

    # Argumento opcional verbose
    parser.add_argument(
        "--solo-concatenar",
        action="store_true",
        help="solo concatena los resultados ya guardados",
    )

    # Argumento opcional verbose
    parser.add_argument(
        "--solo-traer", action="store_true", help="solo trae los datos de facturación"
    )

    # Argumento opcional verbose
    parser.add_argument(
        "--no-traer", action="store_true", help="no trae los datos de facturación"
    )

    # Ruta al archivo de credenciales
    parser.add_argument(
        "--ruta-credenciales-data-fact",
        type=str,
        help="Ruta al archivo de credenciales para conectarse a la base de datos",
    )

    # Lista de RUCs a buscar
    parser.add_argument(
        "--id-establecimientos-a-buscar",
        type=str,
        nargs="+",
        help="Lista de RUCs que se desean consultar",
    )

    return parser.parse_args()


def main():
    console = Console()
    args = parse_args()
    param_ntraida = args.no_traer
    id_establecimientos_a_buscar = []
    # Validar si se requiere id_establecimientos
    if not param_ntraida:  # si NO activaste --no-traer
        if not args.id_establecimientos_a_buscar:
            console.print(
                "[red]Debes pasar --id-establecimientos-a-buscar si no usas --no-traer[/red]"
            )
            sys.exit(1)
        if not args.ruta_credenciales_data_fact:
            console.print(
                "[red]Debes pasar --ruta-credenciales-data-fact si no usas --no-traer[/red]"
            )
            sys.exit(1)
        if ".psv" in args.id_establecimientos_a_buscar[0]:
            ruta_id_establecimiento = Path(args.id_establecimientos_a_buscar[0])
            try:
                if not ruta_id_establecimiento.exists():
                    raise FileNotFoundError(
                        f"No se encontró la tabla a la que referencia --id-establecimientos-a-buscar. (SE BUSCO EN {ruta_id_establecimiento.resolve()})"
                    )
                tabla = pl.read_csv(ruta_id_establecimiento, separator="|")
                id_establecimientos_a_buscar = list(
                    tabla["id_establecimiento"].cast(pl.Utf8)
                )
            except FileNotFoundError as e:
                console.print(f"[red]{e}")
                sys.exit(1)
        else:
            id_establecimientos_a_buscar = args.id_establecimientos_a_buscar

    param_concatenar = args.solo_concatenar
    param_pivote = args.solo_pivotear
    param_traida = args.solo_traer
    verbose = args.verbose
    if not param_ntraida:
        ruta_credenciales_data_fact = Path(args.ruta_credenciales_data_fact)
        with console.status(
            "trayendo las facturas de los lugares especificados"
        ) as status:
            leer_y_guardar_datos_mysql(
                id_establecimientos_a_buscar=id_establecimientos_a_buscar,
                ruta_credenciales_data_fact=ruta_credenciales_data_fact,
                param_verbose=verbose,
            )
            status.update("Se termino de traer todos los datos.")
    if not param_traida:
        if param_concatenar:
            with console.status("Transformando las facturas recibidas") as status:
                transformacion_backups(
                    param_pivote=False,
                    param_concatenar=True,
                    param_verbose=verbose,
                )
        else:
            if param_pivote:
                with console.status("Transformando las facturas recibidas") as status:
                    transformacion_backups(
                        param_pivote=True,
                        param_concatenar=False,
                        param_verbose=verbose,
                    )
            else:
                with console.status("Transformando las facturas recibidas") as status:
                    transformacion_backups(
                        param_pivote=True,
                        param_concatenar=True,
                        param_verbose=verbose,
                    )


if __name__ == "__main__":
    main()
