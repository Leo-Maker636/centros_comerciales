from busqueda_rucs import encontrar_locales
from rich.console import Console
from rich.markup import escape
import argparse
from typing import List, Tuple, Optional

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
    ("Recreo", "recreo"),
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


def main():
    args = parse_args()
    console = Console()
    verbose = args.verbose

    for cc_nombre in args.centros_comerciales:
        mapping_result = mapping(cc_nombre)
        if mapping_result is None:
            console.print(
                f"[bold red]No se encontró el centro comercial '{escape(cc_nombre)}' en la lista de mapeo.[/bold red]"
            )
            continue

        nombre_cc, palabra_clave = mapping_result
        console.print(
            f"[bold gray]Procesando centro comercial '{escape(nombre_cc)}' con palabra clave '{escape(palabra_clave)}'...[/bold gray]"
        )

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


if __name__ == "__main__":
    main()
