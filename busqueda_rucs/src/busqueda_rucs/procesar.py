from rich.console import Console
import polars as pl
from polars.exceptions import ColumnNotFoundError, PolarsError
from pathlib import Path
from typing import Dict, Tuple
from Levenshtein import distance as lev_dist
import re, duckdb, unicodedata, time
from importlib.resources import files, as_file

palabras_contexto_espanol = [
    "el",
    "la",
    "los",
    "las",
    "lo",
    "un",
    "una",
    "unos",
    "unas",
    "de",
    "del",
    "al",
    "a",
    "ante",
    "bajo",
    "con",
    "contra",
    "desde",
    "durante",
    "en",
    "entre",
    "hacia",
    "hasta",
    "mediante",
    "para",
    "por",
    "segun",
    "sin",
    "sobre",
    "tras",
    "y",
    "e",
    "o",
    "u",
    "calle",
    "avenida",
    "av",
    "av.",
    "pasaje",
    "psje",
    "paso",
    "barrio",
    "sector",
    "urbanizacion",
    "urb",
    "ciudadela",
    "cdla",
    "km",
    "kilometro",
    "manzana",
    "mz",
    "solar",
    "lote",
    "etapa",
    "bloque",
    "edificio",
    "edif",
    "oficina",
    "of",
]


def resolver_rutas() -> Dict[str, Path]:
    try:
        METARUTA_PACKAGE = files(
            "busqueda_rucs"
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
    except FileNotFoundError as e:
        raise FileNotFoundError(e)

    return {"info_cc": RUTA_base_info_cc, "rucs_sri": RUTA_base_rucs_sri}


def _normalizar(s: str) -> str:
    if s == "":
        return ""
    s = s.lower()  # .lower() lowercase s
    s = unicodedata.normalize(
        "NFD", s
    )  # .normalize("NFD") is a method which decompose an special character as 'á' into 'a + ´',
    # where "NFD" stands for Normalization From Decomposed
    s = "".join(
        c for c in s if unicodedata.category(c) != "Mn"
    )  # Eliminamos los espacios y acentos. En este caso unicodedata.cato
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def delimitar_busqueda_establecimientos(
    ruta_base_rucs_sri: Path,
    cc_nombre: str,
    provincia: str,
    canton: str,
    parroquias_posibles: str,
    perimetro_calles: str,
    param_verbose: bool = False,
) -> pl.DataFrame:
    """
    Esta parte realiza una delimitación según %PROVINCIA%/%CANTON%/%PARROQUIA% en los que el centro_comercial se encuentra.
    """

    parroquias_posibles_regexp = "|".join(parroquias_posibles)
    regexp_ppc = (
        r"(?i)^\s*"
        + f"{provincia}"
        + r"\s*/\s*"
        + f"{canton}"
        + r"\s*/\s*.*("
        + f"{parroquias_posibles_regexp}"
        + r").*"
    )
    nombres_calles = perimetro_calles
    nombres_significativos = []

    for nombre_calle in nombres_calles:
        palabras = nombre_calle.split(" ")
        palabras_significativas = [
            palabra for palabra in palabras if palabra not in palabras_contexto_espanol
        ]
        nombres_significativos.extend(palabras_significativas)

    regexp_calles = r"(?i)(" + "|".join(nombres_significativos) + ")"
    if param_verbose:
        mensaje_verbose = f"Para delimitar {cc_nombre} usamos las siguientes [bold]regexp:\n[blue bold]regexp provincia, canton, parroquia:[/blue bold]\t\t[green]{regexp_ppc}[/green]\n[blue bold]regexp perimetro calles:[/blue bold]\t\t[green]{regexp_calles}[/green]"
        Console().print(mensaje_verbose)

    try:
        base_rucs_cerca: pl.DataFrame = (
            pl.scan_parquet(ruta_base_rucs_sri)
            .filter(pl.col("direccion_completa") != "")
            .with_columns(
                pl.col("direccion_completa")
                .str.contains(
                    regexp_ppc,
                    literal=False,  # (?i) = case insensitive
                )
                .alias("cerca_CC")
            )
            .filter((pl.col("cerca_CC") == True))
            .with_columns(
                pl.col("direccion_completa")
                .str.contains(
                    regexp_calles,
                    literal=False,
                )
                .alias("cerca_CC")
            )
            .filter((pl.col("cerca_CC") == True))
            .with_columns(
                pl.col("nombre_fantasia_comercial")
                .map_elements(lambda x: _normalizar(x))
                .alias("nombre_fantasia_comercial"),
                pl.when(
                    pl.col("numero_ruc")
                    .cast(pl.Int64)
                    .cast(pl.String)
                    .str.starts_with("1")
                )
                .then(pl.col("numero_ruc").cast(pl.Int64).cast(pl.String))
                .otherwise(
                    (pl.lit("0") + pl.col("numero_ruc").cast(pl.Int64).cast(pl.String))
                )
                .alias("numero_ruc"),
                pl.col("id_establecimiento").cast(pl.Int64).alias("id_establecimiento"),
            )
            .select(
                pl.col("numero_ruc"),
                pl.col("razon_social"),
                pl.col("numero_establecimiento"),
                pl.col("id_establecimiento"),
                pl.col("nombre_fantasia_comercial"),
                pl.col("direccion_completa"),
                pl.col("estado_contribuyente"),
            )
            .collect()
        )
        if param_verbose:
            tamano_original = (
                pl.scan_parquet(ruta_base_rucs_sri).select(pl.count()).collect()[0, 0]
            )
            tamano_delimitacion = len(base_rucs_cerca)
            Console().print(
                f"Se ha delimitado la base_rucs_sri, obteniendo {tamano_delimitacion} de {tamano_original} la tabla original."
            )
    except ColumnNotFoundError as e:
        raise ColumnNotFoundError(e)
    except PolarsError as e:
        raise PolarsError(e)
    except Exception as e:
        raise Exception(e)

    return base_rucs_cerca


def fuzzy_mapping(
    tb: pl.DataFrame, nombre: str, set_bias: set, cc: str, threshold_lev_qgram=0.9
) -> pl.DataFrame:
    """
    Realiza un mapeo difuso entre los valores de una columna de una tabla y un conjunto de candidatos.

    Esta función compara los valores de la columna especificada en el DataFrame con un conjunto
    de elementos candidatos (`set_bias`) utilizando una combinación de similitud basada en q-gramas
    y la distancia de Levenshtein. Primero se filtran coincidencias aproximadas usando q-gramas
    según un umbral, y luego se refina la coincidencia aplicando Levenshtein para obtener un
    puntaje más preciso de similitud.

    Args:
        `tb` (pl.DataFrame): El DataFrame que contiene la columna a mapear.
        `nombre` (str): El nombre de la columna en `tb` cuyos valores serán comparados.
        `set_bias` (set): Conjunto de valores candidatos para hacer el mapeo difuso.
        `cc` (str): Nombre de la columna de salida que contendrá los valores mapeados.
        `threshold_lev_qgram` (float, optional): Umbral de similitud para el prefiltrado por q-gramas
            antes de aplicar la distancia de Levenshtein. Valor por defecto es 0.9.

    Returns:
        pl.DataFrame: Una copia del DataFrame original con una nueva columna (`cc`) que contiene
        los valores del conjunto candidato más similares según el procedimiento de mapeo difuso.
    """

    def levenshtein_similarity(s1, s2):
        # Calcula un score de 0 a 1 basado en la distancia
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        return 1 - (lev_dist(s1, s2) / max_len)

    def _qgrams(s, q=3) -> set:
        """
        Encontrar qgramas para una palabra
        """
        return {s[i : i + q] for i in range(len(s) - q + 1)}

    def _jaccard_similarity(a: set, b: set) -> float:
        """
        score de empate. Corazon para la comparación de los qgramas.
        """
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def _match_condition(
        s: str,
        dict_qgramas: Dict[str, set],
        minimumthreshold=0.28,
        treshold_inf_segundo_filtro=0.4,
    ) -> Tuple[str, float]:
        s_normalizado = _normalizar(s.lower().replace(cc, "").strip())
        qgram_s = _qgrams(s_normalizado)

        mejor, score = "", 0.0
        for k, qgram_k in dict_qgramas.items():
            sim = _jaccard_similarity(qgram_s, qgram_k)
            if sim > score:
                mejor, score = k, sim

        if score >= threshold_lev_qgram:
            return mejor, score
        elif treshold_inf_segundo_filtro <= score < threshold_lev_qgram:
            score_lev = levenshtein_similarity(s_normalizado, mejor)

            if score_lev > threshold_lev_qgram:
                return mejor, score_lev

        elif (score >= minimumthreshold) & (cc in s.lower()):
            return mejor, 1.0
        return mejor, score

    dict_qgramas_bias = {local: _qgrams(_normalizar(local)) for local in set_bias}

    tabla_con_indicadores = tb.with_columns(
        pl.col(nombre)
        .map_elements(lambda x: _match_condition(x, dict_qgramas=dict_qgramas_bias)[0])
        .alias("mejor_candidato"),
        pl.col(nombre)
        .map_elements(
            lambda x: _match_condition(x, dict_qgramas_bias)[1],
            return_dtype=pl.Float64,
        )
        .alias("score_filtrado"),
    )

    return tabla_con_indicadores


def nearness_mapping(
    tb: pl.DataFrame,
    columna_direccion: str,
    perimetro_calles: str,
    set_contexto: set,
) -> pl.DataFrame:
    """
    Asigna o agrupa valores de direcciones en un DataFrame según proximidad o similitud.

    Esta función analiza los valores de la columna de direcciones especificada y realiza un
    mapeo basado en cercanía o similitud geográfica o textual entre ellos. Puede ser útil
    para normalizar, agrupar o vincular direcciones que son similares pero no idénticas.

    Args:
        `tb` (pl.DataFrame): El DataFrame que contiene la columna de direcciones.
        `columna_direccion` (str): Nombre de la columna cuyas direcciones serán procesadas
            para encontrar coincidencias cercanas o similares.

    Returns:
        pl.DataFrame: Una copia del DataFrame original con la columna de direcciones procesada,
        mostrando valores agrupados o mapeados según proximidad o similitud.
    """
    calles_principales = perimetro_calles

    def _calcular_score_regexp(direccion: str) -> Tuple[float, str]:
        if not direccion:
            return 0.0, ""

        # 1. Extraer la sección de calles (PROVINCIA/CANTON/PARROQUIA/SECTOR/CALLES)
        partes = direccion.split("/")
        dir_calles_raw = partes[3] if len(partes) > 3 else direccion

        # 2. LIMPIEZA Y TOKENIZACIÓN (El "Flojo" Inteligente)
        # re.split(r"[.\s]+") separa por puntos y espacios: "JOHN F. KENNEDY" -> {"john", "f", "kennedy"}
        # Usar un SET elimina el problema de buscar "letras en la mitad" (como ANA en CARDENAS)
        palabras_en_direccion = set(
            p.lower() for p in re.split(r"[.\s]+", dir_calles_raw) if p
        )

        # 3. DEFINICIÓN DE PESOS (Sets para búsqueda instantánea O(1))
        # Desglosamos las calles principales en palabras individuales
        set_principales = set()
        nombres_significativos = []
        for nombre_calle in calles_principales:
            palabras = nombre_calle.split(" ")
            palabras_significativas = [
                palabra
                for palabra in palabras
                if palabra not in palabras_contexto_espanol
            ]
            nombres_significativos.extend(palabras_significativas)
        for calle in nombres_significativos:
            set_principales.add(calle.lower())

        suma_scores = 0.0

        # 4. CÁLCULO DEL SCORE (Comparación exacta de palabra por palabra)
        for palabra in palabras_en_direccion:
            # Aquí ya no hay "in string", hay "in set", lo que garantiza que la palabra sea idéntica
            if palabra in set_principales:
                suma_scores += 1.0  # Peso para nombres de calles clave
            elif palabra in set_contexto:
                suma_scores += (
                    2.0  # Peso para contexto específico (según tu lógica original)
                )

        return float(suma_scores), dir_calles_raw

    palabras_principales = [p for calle in calles_principales for p in calle.split()]

    tabla_con_score_direccion = tb.with_columns(
        pl.col(columna_direccion)
        .map_elements(lambda x: _calcular_score_regexp(x)[0])
        .alias("score_direccion"),
    ).with_columns(
        # Normalización: (valor / max) * 2
        (pl.col("score_direccion") / len(palabras_principales) * 2)
        .fill_nan(0)
        .alias("score_direccion")
    )

    return tabla_con_score_direccion


def encontrar_locales(
    cc_metadata: Tuple[str, str],
    threshold_filtro: float,
    threshold: float = 0.8,
    param_verbose: bool = False,
    frecuencia_minima: int = 1,
):
    """
    Busca locales en un centro comercial según una palabra clave.

    Esta función permite identificar y filtrar locales dentro de un centro comercial
    a partir de información de metadata. Se recibe el nombre del centro comercial y
    una palabra clave, y se retornan los locales que coinciden con dicha información.

    Args:
        `cc_metadata` (tuple of str): Tupla con dos elementos:
            - El nombre del centro comercial en la base de datos.
            - Una palabra clave para filtrar los locales dentro de ese centro.
        `threshold` (float): Indicador sobre el momento en que se debe usar la distancia de Levenshtein.

    Returns:
        pl.DataFrame: Un DataFrame con los locales encontrados que coinciden con el centro
        comercial y la palabra clave proporcionados.
    """
    # Preparar los mensajes para consola
    console = Console()

    rucs_cerca = None
    set_nombres_fantasia_normalizado = None
    cc_nombre_cc_base = cc_metadata[0]
    cc_palabra_clave = cc_metadata[1]
    perimetro_calles_cc = None
    set_contexto_cc = None
    RUTA_base_info_cc = None
    # Establecer la conexion con la base del proyecto
    with console.status(
        "[bold yellow]Procesando info_cc y rucs_sri_cercanos ..."
    ) as status:
        try:
            RUTAS = resolver_rutas()
            RUTA_base_info_cc = RUTAS["info_cc"]
            RUTA_base_rucs_sri = RUTAS["rucs_sri"]

            inicio_conexion_base_info_cc = time.perf_counter()
            base = duckdb.connect(RUTA_base_info_cc, read_only=True)
            base.query("SELECT 1 FROM locales LIMIT 1")
            fin_conexion_base_info_cc = time.perf_counter()
            if param_verbose:
                console.log(
                    f"[white]Conexion Exitosa a info_cc.db!\nTiempo: {fin_conexion_base_info_cc - inicio_conexion_base_info_cc:.4f} segundos"
                )

            # Un chequeo para poder continuar con el proceso. Consiste en que los argumentos de metadata existan para nosotros.
            try:
                cc_nombres_cc_base_disponibles = (
                    (base.query("SELECT DISTINCT centro_comercial FROM locales"))
                    .df()["centro_comercial"]
                    .to_list()
                )
                if param_verbose:
                    console.log(
                        "[white]Se ha rescatado los nombres de locales de la base info_cc"
                    )

                if not cc_nombre_cc_base in cc_nombres_cc_base_disponibles:
                    raise KeyError(
                        f"No existe el centro comercial elegido dentro de la base de datos."
                    )
            except KeyError:
                raise
            # Tomar la base donde buscamos primariamente, esta es base_rucs_sri. Veremos que luego
            # eliminamos está variable pues vamos localizando más la busqueda
            try:
                if not Path(RUTA_base_rucs_sri).exists():
                    raise FileNotFoundError("No se pudo encontrar la base de rucs_sri.")
                ruta_base_rucs_sri = Path(RUTA_base_rucs_sri)
                row = (
                    base.query(
                        f"SELECT provincia, canton, parroquia, perimetro_calles FROM centros_comerciales WHERE centro_comercial = '{cc_nombre_cc_base}';"
                    )
                ).fetchone()
                if not row:
                    raise ValueError(
                        f"No se encontro información de ubicación para {cc_nombre_cc_base}"
                    )
                (
                    provincia_cc,
                    canton_cc,
                    parroquias_posibles_cc,
                    perimetro_calles_cc,
                ) = row
                rucs_cerca = delimitar_busqueda_establecimientos(
                    ruta_base_rucs_sri=ruta_base_rucs_sri,
                    cc_nombre=cc_nombre_cc_base,
                    provincia=provincia_cc,
                    canton=canton_cc,
                    parroquias_posibles=parroquias_posibles_cc,
                    perimetro_calles=perimetro_calles_cc,
                    param_verbose=param_verbose,
                )
                # Elimina
                del ruta_base_rucs_sri
                if param_verbose:
                    console.log(f"[white]Se ha delimitado {len(rucs_cerca)} registros.")
            except Exception as e:
                console.log(f"[red]Error al delimitar la busqueda:\n{e}")
                raise

            # En esta sección normalizamos todos los locales que hayamos podido extraer.
            try:
                cc_nombres = (
                    base.query(
                        f"SELECT DISTINCT local_CC FROM locales WHERE centro_comercial = '{cc_nombre_cc_base}';"
                    )
                ).df()["local_CC"]
                set_nombres_fantasia = set(cc_nombres)
                set_nombres_fantasia_normalizado = {
                    _normalizar(local) for local in set_nombres_fantasia
                }
                contexto_cc = base.query(f"""
                    SELECT 
                        palabra 
                    FROM (
                        SELECT 
                            centro_comercial, 
                            unnest(struct_contexto)['palabra'] AS palabra, 
                            unnest(struct_contexto)['frecuencia'] AS frecuencia 
                        FROM centros_comerciales
                    ) 
                    WHERE frecuencia >= {frecuencia_minima} AND centro_comercial = '{cc_nombre_cc_base}';
                    """).df()["palabra"]
                set_contexto_cc = set(contexto_cc)
            except duckdb.DataError as e:
                console.log(
                    f"[red]Se ha encontrado un error al encontrar los 'nombre_fantasia_comercial' a encontrar pero que en la base se llama 'local_CC':\n{e}"
                )
                raise
            except Exception as e:
                console.log(
                    f"[red]Se ha encontrado un error al encontrar los 'nombre_fantasia_comercial' a encontrar pero que en la base se llama 'local_CC':\n{e}"
                )
                raise
            base.close()

            status.update("[bold white]Se ha logrado traer los datos a memoria!")

        except FileNotFoundError as e:
            console.log(f"[red]{e}")
        except duckdb.Error as e:
            console.log(f"[red]Error en la base {RUTA_base_info_cc}. \n{e}")
            status.update("[bold red]Proceso Fallido!!")
            raise
        except Exception as e:
            console.log(
                "[red]Ha ocurrido un error al entrar a la base de datos 'info_cc' que debe estar en"
                f"'ruta-proyecto/bases/info_cc.db'\n El error es el siguiente:\n{e}"
            )
            status.update("[bold red]Proceso Fallido!!")
            raise

    if rucs_cerca is None:
        raise ValueError("No se logró procesar la variable 'rucs_cerca'")
    if set_nombres_fantasia_normalizado is None:
        raise ValueError(
            "No se logró procesar la variable 'set_nombres_fantasia_normalizado'"
        )

    numero_registros = len(rucs_cerca)
    numero_candidatos_para_el_mapping = len(set_nombres_fantasia_normalizado)

    with console.status("[bold yellow] Realizando el mapping...") as status:
        try:
            inicio_mapping = time.perf_counter()
            tabla_filt_qgram_nom_fantasia = fuzzy_mapping(
                rucs_cerca,
                nombre="nombre_fantasia_comercial",
                set_bias=set_nombres_fantasia_normalizado,
                threshold_lev_qgram=threshold,
                cc=cc_palabra_clave,
            )
            if (not perimetro_calles_cc) or (type(set_contexto_cc) is not set):
                raise ValueError(
                    f"No se pudo encontrar información sobre calles y 'contexto' para {cc_nombre_cc_base}"
                )

            #             tabla_final = tabla_filt_qgram_nom_fantasia.with_columns(
            #                 pl.lit(1).alias("score_direccion")
            #             )

            tabla_final = nearness_mapping(
                tabla_filt_qgram_nom_fantasia,
                "direccion_completa",
                perimetro_calles=perimetro_calles_cc,
                set_contexto=set_contexto_cc,
            )

            tabla_final = tabla_final.with_columns(
                (pl.col("score_filtrado") * 2).alias("score_nombre_normalizado")
            ).with_columns(
                (pl.col("score_nombre_normalizado") * pl.col("score_direccion")).alias(
                    "score_producto_final"
                )
            )
            tabla_final = tabla_final.filter(
                pl.col("score_producto_final") >= threshold_filtro
            )
            fin_mapping = time.perf_counter()
            console.log(
                f"[white]Se logró mappear una tabla de [bold]{numero_registros}[/bold] registros con [bold]{numero_candidatos_para_el_mapping}[/bold] candidatos para mapping sobre la columna 'nombre_fantasia_comercial'."
            )
            console.log(
                f"[white]Se ha filtrado por score y se tienen [bold]{len(tabla_final)}[/bold] candidatos"
            )
            console.log(
                f"[white]Conexion Exitosa a info_cc.db!\nProcesamiento exitoso!\nTiempo: {fin_mapping - inicio_mapping:.4f} segundos"
            )
        except Exception as e:
            console.log(f"[red]Hubo un error al realizar el mappeo:\n{e}")
            status.update("[bold red] No sé pudó mappear la tabla.")
            raise

    return tabla_final
