import duckdb, polars as pl, xlsxwriter
from pathlib import Path
from rich.console import Console
from typing import Any, Dict
from importlib.resources import files, as_file


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
        RUTA_base_info_cc = RUTA_PROYECTO.parent / "bases/info_cc.db"
        if not RUTA_base_info_cc.exists():
            raise FileNotFoundError(
                f"No se encontró el directorio de la base info_cc.db    (SE INTENTO ENCONTRAR ESTE DIRECTORIO {RUTA_base_info_cc.resolve()})"
            )
        RUTA_backups = RUTA_PROYECTO / "backups"
        RUTA_salida_pivote = RUTA_PROYECTO.parent / "resultado_pivote.xlsx"
    except FileNotFoundError as e:
        raise FileNotFoundError(e)

    return {
        "info_cc": RUTA_base_info_cc,
        "RUTA_backups": RUTA_backups,
        "RUTA_salida_pivote": RUTA_salida_pivote,
    }


def concatenar(conexion_duckdb: Any, param_verbose: bool):
    RUTA_backups = resolver_rutas()["RUTA_backups"]
    console = Console()
    try:
        if not RUTA_backups.exists():
            console.print(
                f"[red]No se pudo encontrar el directorio de los backups. (SE BUSCO AQUÍ {RUTA_backups.resolve()})"
            )
            raise FileNotFoundError

        if param_verbose:
            archivos_a_concatenar = "\n".join(
                [str(ruta.resolve()) for ruta in RUTA_backups.glob("*.parquet")]
            )
            console.print(
                f"[blue]La concatenación se hará entre estos archivos:\n{archivos_a_concatenar}"
            )
        placeholder_parquets_concat = str(RUTA_backups) + "/" + "*.parquet"
        conexion_duckdb.execute("DROP TABLE facturacion_cc;")
        conexion_duckdb.execute(f"""
            CREATE TABLE facturacion_cc AS (
                SELECT 
                    * EXCLUDE (anio, mes, dia), 
                    make_timestamp(anio, mes, dia, 0, 0, 0) AS fecha 
                FROM read_parquet('{placeholder_parquets_concat}')
            );
            """)

        numero_de_facturas = conexion_duckdb.execute(
            "SELECT COUNT(*) AS numero_facturas FROM facturacion_cc;"
        ).fetchone()
        numero_de_locales = conexion_duckdb.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT id_establecimiento FROM facturacion_cc);"
        ).fetchone()
        fecha_inicio, fecha_final = conexion_duckdb.execute("""
            SELECT 
                strftime(min(fecha), '%Y/%m') AS fecha_inicio,
                strftime(max(fecha), '%Y/%m') AS fecha_final
            FROM facturacion_cc;
            """).fetchone()
        console.log(
            f"[white]Se ha creado la tabla 'facturacion_cc' con {numero_de_facturas} de {numero_de_locales} estos id_establecimiento desde {fecha_inicio} hasta {fecha_final}."
        )
    except FileNotFoundError:
        raise
    except duckdb.Error as e:
        console.print(f"[red]Hubo un error al concatenar los datos de backups: {e}")
        raise


def pivotear_tabla(
    conexion_duckdb: Any, RUTA_resultado_busqueda_rucs: Path
) -> Dict[str, pl.DataFrame]:
    pivote = {}
    console = Console()
    try:
        pivote["id_establecimiento"] = conexion_duckdb.execute(f"""
            PIVOT(
                SELECT 
                    rbr.centro_comercial,
                    rbr.local_CC,
                    rbr.id_establecimiento,
                    strftime(fcc.fecha, "%Y/%m") AS periodo,
                    SUM(fcc.total) AS total,
                FROM '{RUTA_resultado_busqueda_rucs}' rbr
                LEFT JOIN facturacion_cc fcc
                ON lcl.id_establecimiento = rbr.id_establecimiento
                GROUP BY id_establecimiento
            )
            ON periodo
            USING SUM(total)
            """).pl()
        pivote["categoria"] = conexion_duckdb.execute(f"""
            PIVOT(
                SELECT 
                    rbr.centro_comercial,
                    rbr.local_CC,
                    strftime(fcc.fecha, "%Y/%m") AS periodo,
                    SUM(fcc.total) AS total,
                FROM '{RUTA_resultado_busqueda_rucs}' rbr
                LEFT JOIN facturacion_cc fcc
                ON lcl.id_establecimiento = rbr.id_establecimiento
                GROUP BY categoria
            )
            ON periodo
            USING SUM(total)
            """).pl()
        pivote["centro_comercial"] = conexion_duckdb.execute(f"""
            PIVOT(
                SELECT 
                    rbr.centro_comercial,
                    strftime(fcc.fecha, "%Y/%m") AS periodo,
                    SUM(fcc.total) AS total,
                FROM '{RUTA_resultado_busqueda_rucs}' rbr
                LEFT JOIN facturacion_cc fcc
                ON lcl.id_establecimiento = rbr.id_establecimiento
                GROUP BY centro_comercial
            )
            ON periodo
            USING SUM(total)
            """).pl()
    except duckdb.Error as e:
        console.print(f"[red]No se pudo pivotear los resultados, porque:\n{e}")
    return pivote


def transformacion_backups(
    param_pivote: bool, param_concatenar: bool, param_verbose: bool
):
    console = Console()
    try:
        RUTA_resultado_busqueda_rucs = resolver_rutas()["RUTA_resultado_busqueda_rucs"]
        RUTA_base_info_cc = resolver_rutas()["info_cc"]
        RUTA_salida_pivote = resolver_rutas()["RUTA_salida_pivote"]
        if not RUTA_resultado_busqueda_rucs.exists():
            console.print(
                f"[red]No se encontró la ruta de resultados de busqueda_rucs. (SE INTENTO ESTA RUTA {RUTA_resultado_busqueda_rucs})"
            )
            raise FileNotFoundError
        conexion_duckdb = duckdb.connect(RUTA_base_info_cc)
        if param_concatenar:
            concatenar(conexion_duckdb=conexion_duckdb, param_verbose=param_verbose)
        if param_pivote:
            pivote = pivotear_tabla(
                conexion_duckdb=conexion_duckdb,
                RUTA_resultado_busqueda_rucs=RUTA_resultado_busqueda_rucs,
            )
            with xlsxwriter.Workbook(RUTA_salida_pivote) as workbook:
                for sheetname in pivote.keys():
                    pivote[sheetname].write_excel(
                        workbook=workbook, worksheet=sheetname
                    )

            print(f"Excel generado: {RUTA_salida_pivote}")

    except FileNotFoundError:
        raise
