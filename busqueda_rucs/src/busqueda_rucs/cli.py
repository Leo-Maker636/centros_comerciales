from busqueda_rucs import encontrar_locales
from concurrent.futures import ProcessPoolExecutor, as_completed
from rich.console import Console
from rich.markup import escape
import argparse
import polars as pl
from typing import List, Tuple, Optional, Any

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
        "centros_comerciales",
        type=str,
        nargs="+",
        help="Lista de centros comerciales a procesar",
    )
    return parser.parse_args()


def procesar_cc(cc_nombre: str, verbose: bool) -> Tuple[Any, pl.DataFrame]:
    console = Console()
    with console.capture() as capture:
        mapping_result = mapping(cc_nombre)
        if mapping_result is None:
            console.print(
                f"[bold red]No se encontró el centro comercial '{escape(cc_nombre)}' en la lista de mapeo.[/bold red]"
            )
            return capture, pl.DataFrame()

        nombre_cc, palabra_clave = mapping_result
        console.print(
            f"[bold gray]Procesando centro comercial '{escape(nombre_cc)}' con palabra clave '{escape(palabra_clave)}'...[/bold gray]"
        )
        tabla_resultado = pl.DataFrame()
        try:
            tabla_resultado = encontrar_locales(
                cc_metadata=(nombre_cc, palabra_clave),
                param_verbose=verbose,
            )
            console.print(
                f"[bold green]{escape(nombre_cc)}[/bold green] Proceso finalizado correctamente. "
                f"Se encontraron [bold yellow]{len(tabla_resultado)}[/bold yellow] registros."
            )
        except Exception as e:
            console.print(
                f"[bold red]{escape(nombre_cc)}[/bold red] Error en la ejecución:\n[red]{escape(str(e))}[/red]"
            )
    return capture, tabla_resultado


def main():
    console = Console()
    args = parse_args()
    verbose = args.verbose
    tablas = []
    max_workers = 6

    with ProcessPoolExecutor(max_workers=max_workers) as exec:
        futuros = {
            exec.submit(procesar_cc, cc_nombre, verbose): cc_nombre
            for cc_nombre in args.centros_comerciales
        }

        for future in as_completed(futuros):
            cc_nombre = futuros[future]
            mensajes = ""
            try:
                capture, tabla_cc = future.result()
                mensajes = capture.get()
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
            console.print(mensajes)
            tablas.append(tabla_cc)
    tabla_resultado = pl.concat_list(tablas)
    print(tabla_resultado.head(5))


if __name__ == "__main__":
    main()
