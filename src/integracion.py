from __future__ import annotations

import unicodedata

import pandas as pd


VARIABLES_MEDIDAS = [
    "temperatura_maxima",
    "temperatura_minima",
    "temperatura_media",
    "precipitacion_mm",
    "humedad_relativa",
    "velocidad_viento_kmh",
    "rafagas_viento_kmh",
]

# Fuente A (Open-Meteo, nombres en inglés) -> esquema común.
MAPPING_COLUMNAS = {
    "temperature_max": "temperatura_maxima",
    "temperature_min": "temperatura_minima",
    "temperature_mean": "temperatura_media",
    "precipitation": "precipitacion_mm",
    "relative_humidity": "humedad_relativa",
    "wind_speed": "velocidad_viento_kmh",
    "wind_gust": "rafagas_viento_kmh",
    "date": "fecha",
    "municipality": "municipio",
    "station_id": "estacion_id",
    "source": "fuente_datos",
    "extraction_date": "fecha_extraccion",
}

# Fuente B (estaciones CONAGUA/SMN) -> esquema común.
MAPPING_CONAGUA = {
    "FECHA": "fecha",
    "ESTACION": "estacion_id",
    "MUNICIPIO": "municipio",
    "TMAX": "temperatura_maxima",
    "TMIN": "temperatura_minima",
    "PRECIP": "precipitacion_mm",
    "VIENTO_MS": "velocidad_viento_ms",
    "FUENTE": "fuente_datos",
    "F_EXTRACCION": "fecha_extraccion",
}

# Catálogo de municipios: clave normalizada (sin acentos, minúsculas) -> nombre oficial.
CATALOGO_MUNICIPIOS = {
    "colima": "Colima",
    "villa de alvarez": "Villa de Álvarez",
    "manzanillo": "Manzanillo",
    "tecoman": "Tecomán",
    "comala": "Comala",
}

# Ante un conflicto de valores, la observación in situ de la estación prevalece sobre el modelo.
PRIORIDAD_FUENTES = ["conagua-sintetico", "open-meteo-sintetico"]


def _clave_texto(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.lower().split())


def _fecha_extraccion_utc(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, errors="coerce", utc=True).dt.tz_localize(None)


def homologar_columnas(df: pd.DataFrame, mapeo: dict | None = None) -> pd.DataFrame:
    """Renombra columnas para un esquema común de meteorología."""
    referencia = mapeo or MAPPING_COLUMNAS
    datos = df.rename(columns={k: v for k, v in referencia.items() if k in df.columns and v not in df.columns})
    if "fecha" in datos.columns:
        datos["fecha"] = pd.to_datetime(datos["fecha"], errors="coerce")
    if "fecha_extraccion" in datos.columns:
        datos["fecha_extraccion"] = _fecha_extraccion_utc(datos["fecha_extraccion"])
    return datos


def homologar_catalogos(df: pd.DataFrame) -> pd.DataFrame:
    """Unifica la escritura de municipios y estaciones (mayúsculas, acentos, espacios)."""
    datos = df.copy()
    if "municipio" in datos.columns:
        datos["municipio"] = datos["municipio"].map(
            lambda m: CATALOGO_MUNICIPIOS.get(_clave_texto(m), str(m).strip()) if pd.notna(m) else m
        )
    if "estacion_id" in datos.columns:
        datos["estacion_id"] = datos["estacion_id"].astype(str).str.strip().str.upper()
    return datos


def normalizar_unidades(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte las variables medidas a numérico (float) en las unidades del esquema común."""
    datos = df.copy()
    for col in VARIABLES_MEDIDAS:
        if col in datos.columns:
            datos[col] = pd.to_numeric(datos[col], errors="coerce").astype(float)
    return datos


def preparar_fuente_conagua(df: pd.DataFrame) -> pd.DataFrame:
    """Lleva la fuente B al esquema común resolviendo diferencias de nombres, tipos y unidades."""
    datos = df.rename(columns=MAPPING_CONAGUA).copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"], format="%d/%m/%Y", errors="coerce")
    datos["fecha_extraccion"] = _fecha_extraccion_utc(datos["fecha_extraccion"])

    # Convenciones de captura: "Inap" = lluvia inapreciable (< 0.1 mm) -> 0; "-" o vacío = sin dato.
    precip = datos["precipitacion_mm"].astype(str).str.strip()
    datos["precipitacion_mm"] = precip.replace({"Inap": "0", "INAP": "0", "-": None, "": None})
    for col in ["temperatura_maxima", "temperatura_minima", "velocidad_viento_ms"]:
        datos[col] = datos[col].astype(str).str.strip().replace({"-": None, "": None})

    datos = normalizar_unidades(datos)
    datos["velocidad_viento_kmh"] = pd.to_numeric(datos.pop("velocidad_viento_ms"), errors="coerce") * 3.6
    return homologar_catalogos(datos)


def resolver_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina duplicados exactos dentro de una misma fuente (fecha, estación y fuente)."""
    clave = [c for c in ["fecha", "municipio", "estacion_id", "fuente_datos"] if c in df.columns]
    if not clave:
        return df
    return df.drop_duplicates(subset=clave, keep="last").reset_index(drop=True)


def integrar_fuentes(df1: pd.DataFrame, df2: pd.DataFrame | None = None) -> pd.DataFrame:
    """Fusiona dos fuentes ya homologadas en un registro por (fecha, estación).

    Reglas de resolución de conflictos:
    - Si sólo una fuente tiene el valor, se usa ese valor (complementación).
    - Si ambas lo tienen y difieren, gana la fuente con mayor prioridad (PRIORIDAD_FUENTES)
      y se deja registro en `n_conflictos` / `variables_conflicto`.
    - `fuente_datos` conserva el linaje (p. ej. "conagua-sintetico+open-meteo-sintetico").
    """
    a = homologar_catalogos(normalizar_unidades(resolver_duplicados(df1.copy())))
    if df2 is None:
        a["n_conflictos"] = 0
        a["variables_conflicto"] = ""
        return a

    b = homologar_catalogos(normalizar_unidades(resolver_duplicados(df2.copy())))
    rango = {fuente: i for i, fuente in enumerate(PRIORIDAD_FUENTES)}
    a_gana = a["fuente_datos"].map(rango).fillna(99).min() < b["fuente_datos"].map(rango).fillna(99).min()
    alta, baja = (a, b) if a_gana else (b, a)

    clave = ["fecha", "estacion_id"]
    fusion = alta.merge(baja, on=clave, how="outer", suffixes=("_alta", "_baja"), indicator=True)

    resultado = fusion[clave].copy()
    conflictos = pd.Series([[] for _ in range(len(fusion))], index=fusion.index)
    for col in VARIABLES_MEDIDAS + ["municipio"]:
        vacia = pd.Series(None, index=fusion.index, dtype=float if col in VARIABLES_MEDIDAS else object)
        if col in fusion.columns:
            # Columna presente en una sola fuente: merge no le añade sufijo.
            v_alta = fusion[col] if col in alta.columns else vacia
            v_baja = fusion[col] if col in baja.columns else vacia
        elif f"{col}_alta" in fusion.columns:
            v_alta, v_baja = fusion[f"{col}_alta"], fusion[f"{col}_baja"]
        else:
            continue
        if col in VARIABLES_MEDIDAS:
            v_alta = v_alta.astype(float)
            v_baja = v_baja.astype(float)
            difieren = v_alta.notna() & v_baja.notna() & ((v_alta - v_baja).abs() > 0.05)
        else:
            difieren = v_alta.notna() & v_baja.notna() & (v_alta != v_baja)
        for idx in fusion.index[difieren]:
            conflictos[idx].append(col)
        resultado[col] = v_alta.where(v_alta.notna(), v_baja)

    ambas = fusion["_merge"] == "both"
    resultado["fuente_datos"] = fusion["fuente_datos_alta"].where(fusion["fuente_datos_alta"].notna(), fusion["fuente_datos_baja"])
    resultado.loc[ambas, "fuente_datos"] = fusion.loc[ambas, "fuente_datos_alta"] + "+" + fusion.loc[ambas, "fuente_datos_baja"]
    resultado["fecha_extraccion"] = fusion[["fecha_extraccion_alta", "fecha_extraccion_baja"]].max(axis=1)
    resultado["n_conflictos"] = conflictos.map(len).astype(int)
    resultado["variables_conflicto"] = conflictos.map(lambda v: ",".join(v))

    columnas = ["fecha", "municipio", "estacion_id", *[c for c in VARIABLES_MEDIDAS if c in resultado.columns],
                "fuente_datos", "fecha_extraccion", "n_conflictos", "variables_conflicto"]
    return resultado[columnas].sort_values(clave).reset_index(drop=True)
