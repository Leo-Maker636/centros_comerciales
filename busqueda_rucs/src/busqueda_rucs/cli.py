from busqueda_rucs import encontrar_locales
from concurrent.futures import ProcessPoolExecutor, as_completed
from rich.console import Console
from rich.markup import escape
import argparse
import polars as pl
from typing import List, Tuple, Optional, Dict
from pathlib import Path
from importlib.resources import files, as_file

# Lista de centros comerciales y sus palabras clave
CENTROS_COMERCIALES: List[Tuple[str, str]] = [
    ("Recreo", "recreo"),
    ("Condado Shopping", "condado"),
    ("Mall del Sol", "sol"),
    ("San Marino", "marino"),
    ("Paseo Shopping", "paseo"),
    ("Mall de los Andes", "andes"),
    ("Portal Shopping", "shopping"),
    ("Paseo San Francisco", "francisco"),
    ("El Jardin", "jardin"),
    ("Quicentro", "quicentro"),
    ("Mall del Pacifico", "pacifico"),
]


def resolver_rutas() -> Dict[str, Path]:
    try:
        METARUTA_PACKAGE = files(
            "transformar_fact"
        )  # IMPORTANTE! Mover con cuidado esto, para no romper el proyecto
        # Importante en el pyproject.toml dice:
        # [tool.setuptools.packages.find]
        # where = ["src"]
        # POR ESO LA RUTA DEL PAQUETE REALMENTE ES 'busqueda_rucs/src/busqueda_rucs' Y 'busqueda_rucs/' ES LA
        # RUTA DEL PROYECTO
        RUTA_PROYECTO = None
        with as_file(METARUTA_PACKAGE) as RUTA_PACKAGE:
            RUTA_PROYECTO = RUTA_PACKAGE.parent.parent  # Esta el la ruta busqueda_rucs/

        if not RUTA_PROYECTO:
            raise FileNotFoundError(
                "No se encontró el directorio de la base info_cc.db   (NO SE PUDO OBTENER INFORMACIÓN EN EL CONTEXT MANAGER PARA LA RUTA DEL PROYECTO)"
            )
        elif not RUTA_PROYECTO.exists():
            raise FileNotFoundError(
                "No se encontró el directorio de la base info_cc.db   (NO SE PUDO OBTENER LA RUTA DEL PROYECTO)"
            )
        RUTA_resultado_busqueda_rucs = (
            RUTA_PROYECTO.parent / "bases/resultado_busqueda_rucs.psv"
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(e)

    return {
        "RUTA_resultado_busqueda_rucs": RUTA_resultado_busqueda_rucs,
    }


def mapping(nombre_cc: str) -> Optional[Tuple[str, str]]:
    """Dado un nombre de centro comercial, retorna (nombre_real, palabra_clave)."""
    for nombre_real, palabra_clave in CENTROS_COMERCIALES:
        if nombre_cc.lower() == nombre_real.lower():
            return nombre_real, palabra_clave
    return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Búsqueda de RUCs por centros comerciales"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Activa mensajes detallados"
    )
    parser.add_argument(
        "-cc",
        type=str,
        nargs="+",
        help="Lista de centros comerciales a procesar",
    )
    parser.add_argument(
        "--filter",
        type=float,
        nargs="*",
        default=[],
        help="Threshold para filtrar los resultados por score total",
    )
    return parser.parse_args()


def procesar_cc(cc_nombre: str, verbose: bool, threshold_filtro: float) -> pl.DataFrame:
    console = Console()
    mapping_result = mapping(cc_nombre)
    if mapping_result is None:
        console.print(
            f"[bold red]No se encontró el centro comercial '{escape(cc_nombre)}' en la lista de mapeo.[/bold red]"
        )
        return pl.DataFrame()

    nombre_cc, palabra_clave = mapping_result
    console.log(
        f"[bold gray]Procesando centro comercial '{escape(nombre_cc)}' con palabra clave '{escape(palabra_clave)}'...[/bold gray]"
    )
    tabla_resultado = pl.DataFrame()
    try:
        tabla_resultado = encontrar_locales(
            cc_metadata=(nombre_cc, palabra_clave),
            param_verbose=verbose,
            threshold_filtro=threshold_filtro,
        )
        console.print(
            f"[bold green]{escape(nombre_cc)}[/bold green] Proceso finalizado correctamente. "
        )
    except Exception as e:
        console.print(
            f"[bold red]{escape(nombre_cc)}[/bold red] Error en la ejecución:\n[red]{escape(str(e))}[/red]"
        )
    return tabla_resultado


def main():
    console = Console()
    rutas = resolver_rutas()
    args = parse_args()
    verbose = args.verbose
    if args.cc == ["a"]:
        centros_comerciales = [
            "Recreo",
            "Condado Shopping",
            "Mall del Sol",
            "San Marino",
            "Paseo Shopping",
            "Mall de los Andes",
            "Portal Shopping",
            "Paseo San Francisco",
            "El Jardin",
            "Quicentro",
            "Mall del Pacifico",
        ]
    else:
        centros_comerciales = args.cc
    threshold_filtro_lista = args.filter
    default_filter = 0.0
    while len(threshold_filtro_lista) < len(centros_comerciales):
        threshold_filtro_lista.append(default_filter)
    tablas = []
    max_workers = 6

    with ProcessPoolExecutor(max_workers=max_workers) as exec:
        futuros = {
            exec.submit(
                procesar_cc, centros_comerciales[i], verbose, threshold_filtro_lista[i]
            ): i
            for i, _ in enumerate(centros_comerciales)
        }

        for future in as_completed(futuros):
            cc_nombre = futuros[future]
            try:
                tabla_cc = future.result()
            except Exception as e:
                # Error inesperado en el proceso
                console.print(
                    f"[bold red]{cc_nombre}[/bold red] Error crítico: {escape(str(e))}"
                )
                tabla_cc = pl.DataFrame()
                logs = (
                    f"[bold red]{cc_nombre}[/bold red] Error crítico: {escape(str(e))}"
                )
                console.print(logs)
            tablas.append(tabla_cc)
    tabla_resultado = pl.concat(tablas)
    RUTA_resultado_busqueda_rucs = rutas["RUTA_resultado_busqueda_rucs"]
    tabla_resultado.write_csv(RUTA_resultado_busqueda_rucs, separator="|")
    console.print(f"Se ha impreso es resultado en {RUTA_resultado_busqueda_rucs}.")


if __name__ == "__main__":
    main()
