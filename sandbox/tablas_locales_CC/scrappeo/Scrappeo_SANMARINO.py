from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By as BY
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd

categorias_SANMARINO = ["entretenimiento", "gastronomia", "hogar", "moda", "salud-y-estetica", "servicios"]

profile_path = r"C:\Users\anali\AppData\Roaming\Mozilla\Firefox\Profiles\0CsYc6yV.Profile 2"

options = Options()
options.add_argument("-profile")
options.add_argument(profile_path)

options.add_argument("--headless")


options.set_preference("dom.webdriver.enabled", False)
options.set_preference("useAutomationExtension", False)

profile = FirefoxProfile(profile_path)

driver = webdriver.Firefox(
    service=Service(GeckoDriverManager().install()),
    options=options
)

def obtener_html_renderizad_cat(categoria:str) -> BeautifulSoup:
    driver.get(f"https://www.sanmarino.com.ec/locales/?categoria={categoria}")

    wait = WebDriverWait(driver, 30)
    try:
        wait.until(
            EC.presence_of_element_located((BY.CSS_SELECTOR, "body.wp-singular.page.page-id-13 section.w-100"))
        )
    except TimeoutException:
        raise RuntimeError(
            "La página cargó, pero los locales no aparecieron en el tiempo esperado"
        )

    html_renderizado = driver.page_source
    soup = BeautifulSoup(html_renderizado, "html.parser")
    return soup

def extraer_nombres(categoria) -> pd.DataFrame:
    soup = obtener_html_renderizad_cat(categoria)
    cuerpo = soup.find_all("body")[0].find_all("section", class_ = "w-100")[0]
    tabla = cuerpo.find_all("div", class_ = "container")[0].find_all("ul", id = "myList", class_ = "mt-5")[0]
    locales = tabla.find_all("li")
    data = []
    for local in locales:
        primer_span = local.find("span")
        nombre = primer_span.get_text(strip=True) if primer_span else None
        if nombre is None:
            continue
        data.append({
            "LOCAL" : nombre,
            "CENTRO COMERCIAL": "SAN MARINO",
            "CATEGORIA": categoria
        })

    return pd.DataFrame(data)


if __name__ == "__main__":
    locales = []
    for categoria in categorias_SANMARINO:
        locales.append(extraer_nombres(categoria))
    
    San_Marino = pd.concat(locales, ignore_index=True)
    San_Marino.to_csv("San_Marino_locales.tsv", sep = "\t", index=False)
