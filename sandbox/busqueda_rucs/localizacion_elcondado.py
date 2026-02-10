import polars as pl
from pathlib import Path
import unicodedata
import re
from typing import Dict, Tuple
import duckdb
from Levenshtein import distance as lev
import re
from typing import Tuple



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
                r"(?i)^\s*PICHINCHA\s*/\s*QUITO\s*/\s*(PONCEANO|COTOCOLLAO)",
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
    tb: pl.DataFrame, nombre: str, set_bias: set, cc: str, threshold=0.9
) -> pl.DataFrame:
    """
    Filtra una tabla tomando en cuenta los qgramas de cierta columna se parezcan a los de cierto set.
    """
    def levenshtein_similarity(s1, s2):
        # Calcula un score de 0 a 1 basado en la distancia
        max_len = max(len(s1), len(s2))
        if max_len == 0: return 1.0
        return 1 - (lev(s1, s2) / max_len)

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
        s: str, dict_qgramas: Dict[str, set],
        minimumthreshold=0.28,
        treshold_inf_segundo_filtro=0.4,
    ) -> Tuple[str, float]:
        s_normalizado = _normalizar(s.lower().replace(cc, "").strip())
        qgram_s = _qgrams(s_normalizado)

        mejor, score = "", 0.0
        for k, qgram_k in dict_qgramas.items():
            sim = _jaccard(qgram_s, qgram_k)
            if sim > score:
                mejor, score = k, sim

        if score >= threshold:
            return mejor, score
        elif treshold_inf_segundo_filtro <= score < threshold:
            score_lev = levenshtein_similarity(s_normalizado, mejor)

            if score_lev > threshold:
                return mejor, score_lev
        
        elif (score >= minimumthreshold) & (cc in s.lower()):
            return mejor, 1.0
        return "", score

    dict_qgramas_bias = {local: _qgrams(_normalizar(local)) for local in set_bias}

    tabla_filtrada = tb.with_columns(
        pl.col(nombre)
        .map_elements(
            lambda x: _match_qgram_condition(
                x, dict_qgramas=dict_qgramas_bias
            )[0]
        )
        .alias("mejor_candidato"),
        pl.col(nombre)
        .map_elements(
            lambda x: _match_qgram_condition(
                x, dict_qgramas_bias
            )[1],
            return_dtype=pl.Float64,
        )
        .alias("score_filtrado"),
    ).filter((pl.col("mejor_candidato") != ""))

    return tabla_filtrada


def direccion_filtro(
    tb: pl.DataFrame, columna_direccion: str, threshold: float
) -> pl.DataFrame:
     
    def _calcular_score_regexp(direccion: str) -> Tuple[float, str]:
        if not direccion:
            return 0.0, ""

        # 1. Extraer la sección de calles (PROVINCIA/CANTON/PARROQUIA/SECTOR/CALLES)
        partes = direccion.split("/")
        dir_calles_raw = partes[3] if len(partes) > 3 else direccion
        
        # 2. LIMPIEZA Y TOKENIZACIÓN (El "Flojo" Inteligente)
        # re.split(r"[.\s]+") separa por puntos y espacios: "JOHN F. KENNEDY" -> {"john", "f", "kennedy"}
        # Usar un SET elimina el problema de buscar "letras en la mitad" (como ANA en CARDENAS)
        palabras_en_direccion = set(p.lower() for p in re.split(r"[.\s]+", dir_calles_raw) if p)

        # 3. DEFINICIÓN DE PESOS (Sets para búsqueda instantánea O(1))
        # Desglosamos las calles principales en palabras individuales
        set_principales = set()
        for calle in [
            "ANTONIO", "JOSE", "SUCRE", "PRENSA", "JOHN", "KENNEDY", 
            "LEONARDO", "DAVINCI", "MARISCAL"
        ]:
            set_principales.add(calle.lower())

        set_contexto = {
            "av", "san", "cardenas", "caton", "procel", "juan"
        }

        suma_scores = 0.0

        # 4. CÁLCULO DEL SCORE (Comparación exacta de palabra por palabra)
        for palabra in palabras_en_direccion:
            # Aquí ya no hay "in string", hay "in set", lo que garantiza que la palabra sea idéntica
            if palabra in set_principales:
                suma_scores += 1.0  # Peso para nombres de calles clave
            elif palabra in set_contexto:
                suma_scores += 2.0  # Peso para contexto específico (según tu lógica original)

        return float(suma_scores), dir_calles_raw

    calles_principales= [
        "ANTONIO JOSE DE SUCRE",
        "DE LA PRENSA",
        "JOHN F. KENNEDY",
        "LEONARDO DAVINCI",
        "MARISCAL SUCRE",
    ]

    # strings_contexto = [
    #     "av",
    #     "san",
    #     "cardenas",
    #     "caton",
    #     "procel",
    #     "juan"
    # ]

    # calles_objetivo = calles_principales + strings_contexto
    

    # def _calcular_score_regexp(direccion: str) -> Tuple[float, str]:
    #     if not direccion:
    #         return 1.0, ""

    #     dir_calles = direccion.split("/")[
    #         3
    #     ]  # PROVINCIA/CANTON/PARROQUIA/SECTOR/CALLES, me quedo con calles
    #      # Alguna forma de decir que la calle principal cuenta más
    #     suma_scores = 0.0

    #     for calle in calles_objetivo:
    #         palabras_calle = calle.split()

    #         if not palabras_calle:
    #             continue

    #         # Contamos cuántas palabras de la calle objetivo existen en la dirección
    #         aciertos = 0
    #         for palabra in palabras_calle:
    #             # Usamos \b para asegurar que coincida la palabra completa (word boundary)
    #             if re.search(rf"\b{re.escape(palabra)}\b", dir_calles, re.IGNORECASE):
    #                 if palabra in calles_principales:
    #                     aciertos += 1
    #                 elif palabra in  strings_contexto:
    #                     aciertos +=2

    #         # Score de esta calle fija dada por nosotros 
    #         suma_scores += aciertos

    #     # Suma de todos los score
    #     return suma_scores, dir_calles
    
    palabras_principales = [p for calle in calles_principales for p in calle.split()]

    tabla_con_score_direccion = tb.with_columns(
        pl.col(columna_direccion)
        .map_elements(lambda x: _calcular_score_regexp(x)[0])
        .alias("score_direccion"),
        pl.col(columna_direccion)
        .map_elements(lambda x: _calcular_score_regexp(x)[1])
        .alias("calles_direccion"),
        ).with_columns(
        # Normalización: (valor / max) * 2
        (pl.col("score_direccion") / len(palabras_principales) * 2)
        .fill_nan(0)
        .alias("score_direccion")
        )

    return tabla_con_score_direccion


def encontrar_posibles_locales_jardin(threshold: float, threshold_ubicacion: float):
    """
    Proceso principal de emparejamiento de numeros_establecimiento a partir de nombres de locales. Motores: "q-gramas"
    """

    ruta_base_rucs_sri = Path(r"C:\Users\anali\OneDrive - PUBLIPROMUEVE S.A\Ruben Freire's files - CENTROS COMERCIALES\sandbox\bases\base_rucs_sri.parquet")
    rucs_cerca = delimitar_busqueda_establecimientos(
        ruta_base_rucs_sri=ruta_base_rucs_sri
    )
    print("Se logró encontrar los rucs_cerca con ", len(rucs_cerca), "registros.")
    print(
        "Aquí una muestra de las direcciones:\n",
        "\n".join(rucs_cerca.head(15).to_pandas()["direccion_completa"].to_list()[0:5]),
    )

    # En esta sección normalizamos todos los locales que hayamos podido extraer.
    base = duckdb.connect(r"C:/Users/anali/OneDrive - PUBLIPROMUEVE S.A/Ruben Freire's files - CENTROS COMERCIALES/sandbox/bases/info_cc.db")
    condado_nombres = (
        base.query(
            "SELECT DISTINCT local_CC FROM locales WHERE centro_comercial = 'Condado Shopping';"
        )
    ).df()["local_CC"]
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

    tabla_final = tabla_final.with_columns(
        (pl.col("score_filtrado") * 2).alias("score_nombre_normalizado")
    ).with_columns(
        (pl.col("score_nombre_normalizado") * pl.col("score_direccion")).alias("score_producto_final")
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
        threshold=0.85, threshold_ubicacion=0
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

    info_locales = info_locales.select(
        pl.col("numero_ruc"),
        pl.col("numero_establecimiento").cast(pl.Int64),
        pl.col("nombre_fantasia_comercial"),
        pl.col("mejor_candidato"),
        pl.col("score_filtrado"),
        pl.col("score_direccion"),
        pl.col("score_producto_final"),
        pl.col("calles_direccion")
    )

    desc_info = info_locales['nombre_fantasia_comercial'].value_counts().sort("count", descending=False)
    numeros_unos = len(desc_info.filter(
        (pl.col("count") == 1)
    ))
    print(f"Hay estos unos: {numeros_unos}.\n {desc_info}")
    info_locales.write_excel(r"C:\Users\anali\OneDrive - PUBLIPROMUEVE S.A\Ruben Freire's files - CENTROS COMERCIALES\sandbox\busqueda_rucs\primeros_resultados_condado.xlsx")

    #LOS QUE ESTAMOS SEGUROS SON LOS QUE APARECEN UNA SOLA VEZ EN LOS ENCONTRADOS CON BUEN SCORE(DIRRECCION) Y HAY QUE
    #ANLIZAR MAS FINO LOS QUE TIENEN NOMBRE REPETIDO Y CON BUEN SCORE EN NOMBRE.
    print("Se termino!!")
