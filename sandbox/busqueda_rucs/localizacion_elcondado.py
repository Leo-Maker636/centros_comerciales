import polars as pl
from pathlib import Path
import unicodedata
import re
from typing import Dict, Tuple
import duckdb


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


def delimitar_busqueda_establecimientos(ruta_base_rucs_sri: Path) -> pl.DataFrame:
    """
    Esta parte realiza una delimitación según %PROVINCIA%/%CANTON%/%PARROQUIA% en los que el centro_comercial se encuentra.
    """

    base_rucs_cerca: pl.DataFrame = (
        pl.scan_parquet(ruta_base_rucs_sri)
        .filter(pl.col("direccion_completa") != "")
        .with_columns(
            pl.col("direccion_completa")
            .str.contains(
                r"(?i)^\s*PICHINCHA\s*/\s*QUITO\s*/\s*PONCIANO",
                literal=False,  # (?i) = case insensitive
            )
            .alias("cerca_CC")
        )
        .filter((pl.col("cerca_CC") == True))
        .with_columns(
            pl.col("direccion_completa")
            .str.contains(
                r"(?i)(JOSE|SUCRE|PRENSA|JOHN|KENNEDY|LEONARDO|DAVINCI|MARISCAL|SUCRE)",
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
                pl.col("numero_ruc").cast(pl.Int64).cast(pl.String).str.starts_with("1")
            )
            .then(pl.col("numero_ruc").cast(pl.Int64).cast(pl.String))
            .otherwise(
                (pl.lit("0") + pl.col("numero_ruc").cast(pl.Int64).cast(pl.String))
            )
            .alias("numero_ruc"),
        )
        .collect()
    )

    return base_rucs_cerca


def qgram_filtro(
    tb: pl.DataFrame, nombre: str, set_bias: set, cc: str, threshold=0.5
) -> pl.DataFrame:
    """
    Filtra una tabla tomando en cuenta los qgramas de cierta columna se parezcan a los de cierto set.
    """

    def _qgrams(s, q=3) -> set:
        """
        Encontrar qgramas para una palabra
        """
        return {s[i : i + q] for i in range(len(s) - q + 1)}

    def _jaccard(a: set, b: set) -> float:
        """
        score de empate. Corazon para la comparación de los qgramas.
        """
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def _match_qgram_condition(
        s: str, dict_qgramas: Dict[str, set], minimumthreshold: float
    ) -> Tuple[str, float]:
        s = _normalizar(s)
        qgram_s = _qgrams(s)

        mejor, score = "", 0.0
        for k, qgram_k in dict_qgramas.items():
            sim = _jaccard(qgram_s, qgram_k)
            if sim > score:
                mejor, score = k, sim

        if score >= threshold:
            return mejor, score
        elif (score >= minimumthreshold) & (cc in s):
            s_sin_cc = s.replace(cc, "")
            return _match_qgram_condition(
                s_sin_cc,
                dict_qgramas=dict_qgramas,
                minimumthreshold=minimumthreshold * 4,
            )
        return "", score

    dict_qgramas_bias = {local: _qgrams(local, q=3) for local in set_bias}

    tabla_filtrada = tb.with_columns(
        pl.col(nombre)
        .map_elements(
            lambda x: _match_qgram_condition(
                x, dict_qgramas=dict_qgramas_bias, minimumthreshold=0.28
            )[0]
        )
        .alias("mejor_candidato"),
        pl.col(nombre)
        .map_elements(
            lambda x: _match_qgram_condition(x, dict_qgramas_bias, 0.28)[1],
            return_dtype=pl.Float64,
        )
        .alias("score_filtrado"),
    ).filter((pl.col("mejor_candidato") != ""))

    return tabla_filtrada


def direccion_filtro(
    tb: pl.DataFrame, columna_direccion: str, threshold: float
) -> pl.DataFrame:
    calles_objetivo = [
        "ANTONIO JOSE DE SUCRE",
        "DE LA PRENSA",
        "JOHN F. KENNEDY",
        "LEONARDO DAVINCI",
        "MARISCAL SUCRE",
    ]

    def _calcular_score_regexp(direccion: str) -> Tuple[float, str]:
        if not direccion:
            return 1.0, ""

        dir_calles = direccion.split("/")[
            3
        ]  # PROVINCIA/CANTON/PARROQUIA/SECTOR/CALLES, me quedo con calles
        total_calles = (
            len(calles_objetivo) + 5
        )  # Alguna forma de decir que la calle principal cuenta más
        suma_scores = 0.0

        for calle in calles_objetivo:
            palabras_calle = calle.split()

            if not palabras_calle:
                continue

            # Contamos cuántas palabras de la calle objetivo existen en la dirección
            aciertos = 0
            for palabra in palabras_calle:
                # Usamos \b para asegurar que coincida la palabra completa (word boundary)
                if re.search(rf"\b{re.escape(palabra)}\b", dir_calles):
                    aciertos += 1

            # Score de esta calle: palabras_encontradas / total_palabras_calle
            suma_scores += (
                aciertos / len(palabras_calle)
                if calle != "RIO AMAZONAS"
                else 6 * (aciertos / len(palabras_calle))
            )

        # Promedio final sobre el número de calles objetivo
        return suma_scores / total_calles, dir_calles

    tabla_con_score_direccion = tb.with_columns(
        pl.col(columna_direccion)
        .map_elements(lambda x: _calcular_score_regexp(x)[0])
        .alias("score_direccion"),
        pl.col(columna_direccion)
        .map_elements(lambda x: _calcular_score_regexp(x)[1])
        .alias("calles_direccion"),
    )

    return tabla_con_score_direccion.filter(pl.col("score_direccion") >= threshold)


def encontrar_posibles_locales_jardin(threshold: float, threshold_ubicacion: float):
    """
    Proceso principal de emparejamiento de numeros_establecimiento a partir de nombres de locales. Motores: "q-gramas"
    """

    ruta_base_rucs_sri = Path("../bases/base_rucs_sri.parquet")
    rucs_cerca = delimitar_busqueda_establecimientos(
        ruta_base_rucs_sri=ruta_base_rucs_sri
    )
    print("Se logró encontrar los rucs_cerca con ", len(rucs_cerca), "registros.")
    print(
        "Aquí una muestra de las direcciones:\n",
        "\n".join(rucs_cerca.head(15).to_pandas()["direccion_completa"].to_list()[0:5]),
    )

    # En esta sección normalizamos todos los locales que hayamos podido extraer.
    base = duckdb.connect("../bases/info_cc.db")
    condado_nombres = (
        base.query(
            "SELECT DISTINCT local_CC FROM locales WHERE centro_comercial = 'CONDADO';"
        )
    ).df()
    set_nombre_fantasia = set(condado_nombres)
    set_nombre_fantasia_normalizado: set = {
        _normalizar(local) for local in set_nombre_fantasia
    }

    print(
        f"Se tienen {len(set_nombre_fantasia_normalizado)} locales registrados en el CC: Condado."
    )

    tabla_filt_qgram_nom_fantasia = qgram_filtro(
        rucs_cerca,
        "nombre_fantasia_comercial",
        set_nombre_fantasia_normalizado,
        threshold=threshold,
        cc="condado",
    )

    tabla_final = direccion_filtro(
        tabla_filt_qgram_nom_fantasia,
        "direccion_completa",
        threshold=threshold_ubicacion,
    )

    return tabla_final


def filtrar_locales_buena_facturacion(fecha_ini: str, fecha_fin: str):
    """
    Está parte corroborá que los locales seleccionado cumplan con un mínimo de completitud dentro
    de nuestra facturación. Esto implica haber facturado todos los meses del periodo de análisis.
    Además que proporciona un resumen
    """
    pass


if __name__ == "__main__":
    info_locales = encontrar_posibles_locales_jardin(
        threshold=0.92, threshold_ubicacion=0.32
    )
    print(
        "Se filtro las siguientes cosas",
        info_locales.select(
            pl.col("numero_ruc"),
            pl.col("numero_establecimiento").cast(pl.Int64),
            pl.col("nombre_fantasia_comercial"),
            pl.col("mejor_candidato"),
            pl.col("score_filtrado"),
            pl.col("score_direccion"),
            pl.col("calles_direccion"),
        ),
    )

    info_locales.select(
        pl.col("numero_ruc"),
        pl.col("numero_establecimiento").cast(pl.Int64),
        pl.col("nombre_fantasia_comercial"),
        pl.col("mejor_candidato"),
        pl.col("score_filtrado"),
        pl.col("score_direccion"),
        pl.col("calles_direccion"),
    ).write_excel("primeros_resultados_condado.xlsx")

    print("Se termino!!")
