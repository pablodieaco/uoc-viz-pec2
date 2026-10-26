import json
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"

URL_REE = "https://apidatos.ree.es/es/datos/demanda/evolucion"
URL_OWID = "https://ourworldindata.org/grapher/"
PARAMS_OWID = "?v=1&csvType=full&useColumnShortNames=true"
# OWID pide identificar el cliente con este User-Agent
CABECERAS_OWID = {"User-Agent": "Our World In Data data fetch/1.0"}

AÑO_DEMANDA = 2025  # 2026 no ha terminado todavía.
ENTIDADES_RENTA = ["Spain", "World", "European Union (27)"]

# norte a sur para que las gráficas tengan un orden lógico.
PAISES = {
    "NOR": "Noruega",
    "SWE": "Suecia",
    "FIN": "Finlandia",
    "GBR": "Reino Unido",
    "IRL": "Irlanda",
    "DNK": "Dinamarca",
    "DEU": "Alemania",
    "POL": "Polonia",
    "NLD": "Países Bajos",
    "FRA": "Francia",
    "CHE": "Suiza",
    "AUT": "Austria",
    "ITA": "Italia",
    "PRT": "Portugal",
    "ESP": "España",
    "GRC": "Grecia",
}
INICIO_TEMPERATURA = "1980-01-01"
MESES = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


def descargar_owid(nombre: str) -> tuple[pd.DataFrame, dict]:
    """
    Función reutilzable para descargar en formato csv tal y como indican en
    https://ourworldindata.org/grapher en cada gráfico.
    """
    df = pd.read_csv(
        URL_OWID + nombre + ".csv" + PARAMS_OWID, storage_options=CABECERAS_OWID
    )
    respuesta = requests.get(
        URL_OWID + nombre + ".metadata.json" + PARAMS_OWID, timeout=60
    )
    respuesta.raise_for_status()
    return df, respuesta.json()


def guardar_json(datos: dict, ruta: Path) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def descargar_demanda() -> pd.DataFrame:
    """
    Descarga de la demanda diaria de energía electrica en España desde la API
    publicada por Red Eléctrica de España (REE) en https://www.ree.es/es/datos/apidatos

    URL: https://apidatos.ree.es/es/datos/demanda/evolucion?start_date=2025-01-01T00:00&end_date=2025-12-31T23:59&time_trunc=day
    """
    params = {
        "start_date": f"{AÑO_DEMANDA}-01-01T00:00",
        "end_date": f"{AÑO_DEMANDA}-12-31T23:59",
        "time_trunc": "day",
    }
    respuesta = requests.get(URL_REE, params=params, timeout=60)
    respuesta.raise_for_status()
    guardar_json(respuesta.json(), RAW / "demanda_ree_2025.json")

    valores = pd.DataFrame(respuesta.json()["included"][0]["attributes"]["values"])
    demanda = pd.DataFrame(
        {
            "fecha": pd.to_datetime(valores["datetime"].str[:10]),
            "demanda_gwh": valores["value"] / 1000,  # la API da MWh
        }
    )

    logger.info(
        f"Demanda: {len(demanda)} filas, {demanda['fecha'].duplicated().sum()} fechas duplicadas"
    )
    huecos = pd.date_range(f"{AÑO_DEMANDA}-01-01", f"{AÑO_DEMANDA}-12-31").difference(
        demanda["fecha"]
    )
    logger.info(f"Demanda: días que faltan: {len(huecos)}")
    for nombre, fila in [
        ("mín.", demanda.loc[demanda["demanda_gwh"].idxmin()]),
        ("máx.", demanda.loc[demanda["demanda_gwh"].idxmax()]),
    ]:
        logger.info(
            f"Demanda {nombre} {fila['demanda_gwh']:.1f} GWh el {fila['fecha']:%d/%m/%Y}"
        )
    return demanda


def descargar_renta() -> pd.DataFrame:
    """
    Descarga de la renta nacional bruta per cápita por sexo desde Our World in Data
    (https://ourworldindata.org/grapher/gross-national-income-per-capita-males-vs-females)
    """
    df, metadata = descargar_owid("gross-national-income-per-capita-males-vs-females")
    df.to_csv(RAW / "gni_sexo.csv", index=False)
    guardar_json(metadata, RAW / "gni_sexo_metadata.json")

    df["ratio"] = df["gni_pc__sex_female"] / df["gni_pc__sex_male"] * 100
    renta = df[df["entity"].isin(ENTIDADES_RENTA)][
        ["entity", "year", "gni_pc__sex_male", "gni_pc__sex_female", "ratio"]
    ]

    logger.info(
        "Renta de España (hombres, mujeres, ratio):\n"
        + renta[renta["entity"] == "Spain"].to_string(index=False)
    )
    logger.info(f"Renta: nulos: {renta.isna().sum().sum()}")
    logger.info(
        f"Renta: último año por entidad: {renta.groupby('entity')['year'].max().to_dict()}"
    )

    paises = df[df["code"].notna() & ~df["code"].str.startswith("OWID_", na=False)]
    ultimo = paises[paises["year"] == paises["year"].max()]
    extremos = ultimo.loc[[ultimo["ratio"].idxmin(), ultimo["ratio"].idxmax()]]
    logger.info(
        f"Renta: rango del ratio entre países en {ultimo['year'].iloc[0]}:\n"
        + extremos[["entity", "ratio"]].to_string(index=False)
    )
    return renta


def descargar_temperatura() -> pd.DataFrame:
    """
    Descarga de las anomalías de temperatura mensual por país desde Our World in Data
    (https://ourworldindata.org/grapher/country-level-monthly-temperature-anomalies)
    """
    df, metadata = descargar_owid("country-level-monthly-temperature-anomalies")
    df.to_csv(RAW / "temperatura_anomalias.csv", index=False)
    guardar_json(metadata, RAW / "temperatura_metadata.json")

    # el CSV viene en formato ancho (una columna por mes): se pasa a una fila por mes
    largo = df[df["code"].isin(PAISES)].melt(
        id_vars=["code", "year"],
        value_vars=MESES,
        var_name="mes",
        value_name="anomalia",
    )
    largo["fecha"] = pd.to_datetime(
        largo["year"].astype(str)
        + "-"
        + (largo["mes"].map(MESES.index) + 1).astype(str)
        + "-01"
    )
    largo["pais"] = pd.Categorical(
        largo["code"].map(PAISES), categories=PAISES.values(), ordered=True
    )
    temperatura = largo[
        (largo["fecha"] >= INICIO_TEMPERATURA) & largo["anomalia"].notna()
    ][["pais", "fecha", "anomalia"]].sort_values(["pais", "fecha"])

    logger.info(
        f"Temperatura: {temperatura['pais'].nunique()} países, {len(temperatura)} filas\n"
        + temperatura.groupby("pais", observed=True)["fecha"]
        .agg(["min", "max", "count"])
        .to_string()
    )
    logger.info(
        "Temperatura: distribución de |anomalía| (°C):\n"
        + temperatura["anomalia"].abs().describe().round(2).to_string()
    )
    return temperatura


if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    descargar_demanda().to_csv(PROCESSED / "demanda_diaria_2025.csv", index=False)
    descargar_renta().to_csv(PROCESSED / "renta_sexo.csv", index=False)
    descargar_temperatura().to_csv(PROCESSED / "anomalias_europa.csv", index=False)

    (RAW / "fecha_descarga.txt").write_text(date.today().isoformat(), encoding="utf-8")
    logger.success(f"Descarga terminada el {date.today():%d/%m/%Y}")
