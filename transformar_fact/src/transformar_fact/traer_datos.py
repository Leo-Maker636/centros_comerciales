from rich.console import Console
import polars as pl
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv
from contextlib import closing
from mysql.connector import ProgrammingError
import mysql.connector, os, sqlparse, re
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
        RUTA_base_rucs_sri = RUTA_PROYECTO.parent / "bases/base_rucs_sri.parquet"
        if not RUTA_base_rucs_sri.exists():
            raise FileNotFoundError(
                f"No se encontró el directorio de la base base_rucs_sri    (SE INTENTO ENCONTRAR ESTE DIRECTORIO {RUTA_base_rucs_sri.resolve()})"
            )

        RUTA_sql_executables = (
            RUTA_PROYECTO / "src/transformar_fact/consulta_formato.sql"
        )
        if not RUTA_sql_executables.exists():
            raise FileNotFoundError(
                f"No se encontró el directorio de los formatos de consultas consulta_formato.sql   (SE INTENTO ENCONTRAR ESTE DIRECTORIO {RUTA_sql_executables.resolve()})"
            )
        RUTA_backups = RUTA_PROYECTO / "backups"
    except FileNotFoundError as e:
        raise FileNotFoundError(e)

    return {
        "info_cc": RUTA_base_info_cc,
        "rucs_sri": RUTA_base_rucs_sri,
        "RUTA_sql_executables": RUTA_sql_executables,
        "RUTA_backups": RUTA_backups,
    }


def guardar_resultados(
    query: str,
    fecha: str,
    cur: Any,
    RUTA_backups: Path,
    batch_size: int = 80000,
):
    """
    Ejecuta un query en MySQL, obtiene los resultados en batches, y los guarda como archivo Parquet.

    Args:
        query (str): Consulta SQL a ejecutar.
        fecha (str): Fecha que se usará en el nombre del archivo.
        cur (mysql.connector.cursor): Cursor de MySQL ya conectado.
        RUTA_backups (Path): Ruta del directorio donde se guardará el parquet.
        batch_size (int): Tamaño de cada batch para fetchmany.
    """
    console = Console()
    cur.execute(query)

    all_rows = []
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        all_rows.extend(rows)  # acumula todas las filas en memoria

    total_filas = len(all_rows)
    if total_filas == 0:
        console.print(f"[yellow]No hay datos para guardar para {fecha}[/yellow]")
        return

    console.print(f"[green]Se obtuvieron {total_filas} filas en total[/green]")

    # Obtener nombres de columnas
    columnas = [desc[0] for desc in cur.description]

    # Convertir a LazyFrame de Polars
    df_polars = pl.LazyFrame(all_rows, schema=columnas)

    # Guardar como parquet en modo streaming
    df_polars.sink_parquet(
        RUTA_backups / f"facturas_{fecha}.parquet", engine="streaming", mkdir=True
    )

    console.print(
        f"[blue]Archivo guardado en {RUTA_backups / f'facturas_{fecha}.parquet'}[/blue]"
    )


def leer_y_guardar_datos_mysql(
    ruta_credenciales_data_fact: Path, rucs_a_buscar: List[str]
):
    RUTA_sql_executables = resolver_rutas()["RUTA_sql_executables"]
    RUTA_backups = resolver_rutas()["RUTA_backups"]
    console = Console()
    rucs_a_buscar_sql = ",".join(["'" + ruc + "'" for ruc in rucs_a_buscar])
    try:
        if not ruta_credenciales_data_fact.exists():
            console.print()
            raise FileNotFoundError(
                "No se ha encontrado el archivo de variables de entorno."
            )
        if not RUTA_sql_executables.exists():
            console.print()
            raise FileNotFoundError(
                "No se ha encontrado el archivo de traida sql que debe llamarse `consulta_formato.sql`."
            )

        load_dotenv(ruta_credenciales_data_fact, override=True)
        user = os.getenv("USER_DATABASE")
        password = os.getenv("PASSWORD_DATABASE")
        host = os.getenv("HOST_DATABASE")
        database = os.getenv("NAME_DATABASE")
        port = os.getenv("PORT_DATABASE")
        if (not user) or (not password) or (not host) or (not database) or (not port):
            raise ValueError(
                "No se ha encontrado una de las siguientes variables de entorno: `user`, `password`, `host`, `database`, `port`."
            )
        conexion = mysql.connector.connect(
            host=host, user=user, password=password, database=database, port=port
        )
        sql_text = ""
        with open(RUTA_sql_executables, "r", encoding="utf8") as file:
            sql_text = file.read()
        queries = [
            q.strip().replace("{rucs_a_buscar}", rucs_a_buscar_sql)
            for q in sqlparse.split(sql_text)
            if q.strip()
        ]
        with closing(conexion) as conn:
            for query in queries:
                fecha_match = re.search("[0-9]{4}_[0-9]{2}", query)
                if not fecha_match:
                    continue
                fecha = fecha_match.group(0)
                with conn.cursor() as cur:
                    guardar_resultados(
                        cur=cur, fecha=fecha, query=query, RUTA_backups=RUTA_backups
                    )
    except ProgrammingError as e:
        console.print(f"[red] El motor de MySQL reporta el siguiente error:\n{e}")
    except FileNotFoundError:
        raise
