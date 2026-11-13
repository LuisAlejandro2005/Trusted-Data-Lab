from __future__ import annotations

import pandas as pd


VARIABLES_CONTINUAS = [
    "temperatura_maxima",
    "temperatura_minima",
    "temperatura_media",
    "precipitacion_mm",
    "humedad_relativa",
    "velocidad_viento_kmh",
    "rafagas_viento_kmh",
]

# Variables observadas contra las que se contrasta la ausencia (para distinguir MCAR de MAR).
VARIABLES_CONTEXTO = ["fuente_datos", "estacion_id", "municipio", "mes"]
UMBRAL_DIFERENCIA_MAR = 0.20  # diferencia de tasas de ausencia entre grupos (20 puntos porcentuales)


def diagnosticar_faltantes(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve conteos y porcentajes de nulos por columna."""
    total = len(df)
    resumen = pd.DataFrame({
        "nulos": df.isna().sum(),
        "porcentaje": (df.isna().sum() / total * 100).round(2),
    })
    return resumen.sort_values("porcentaje", ascending=False)


def identificar_patrones_ausencia(df: pd.DataFrame) -> pd.DataFrame:
    """Resume patrones de ausencia por variable, agrupados por mes y municipio."""
    if {"mes", "municipio"}.issubset(df.columns):
        claves = [df["mes"], df["municipio"]]
        return (
            df.drop(columns=["mes", "municipio"])
            .isna()
            .groupby(claves)
            .sum()
            .reset_index()
        )
    return pd.DataFrame({"mensaje": ["No se detectaron columnas para identificar patrones temporales."]})


def diagnosticar_mecanismo_por_variable(df: pd.DataFrame) -> pd.DataFrame:
    """Clasifica el mecanismo de ausencia de cada variable con nulos.

    Criterio: si la tasa de ausencia cambia fuertemente según una variable observada
    (fuente, estación, municipio o mes), la ausencia depende de datos observados -> MAR.
    Si es homogénea en todos los grupos, es compatible con MCAR. MNAR (la ausencia depende
    del propio valor no observado) no puede probarse con los datos; se anota como riesgo
    cuando la variable es susceptible (p. ej. pluviómetros que fallan con lluvias extremas).
    """
    filas = []
    contexto = [c for c in VARIABLES_CONTEXTO if c in df.columns]
    for col in [c for c in VARIABLES_CONTINUAS if c in df.columns]:
        faltantes = df[col].isna()
        if not faltantes.any():
            continue
        mayor_dif, asociada = 0.0, ""
        for ctx in contexto:
            tasas = faltantes.groupby(df[ctx]).mean()
            if len(tasas) > 1 and tasas.max() - tasas.min() > mayor_dif:
                mayor_dif, asociada = float(tasas.max() - tasas.min()), ctx
        if mayor_dif > UMBRAL_DIFERENCIA_MAR:
            mecanismo = "MAR"
            justificacion = f"La ausencia depende de '{asociada}' (diferencia de {mayor_dif:.0%} entre grupos)."
        else:
            mecanismo = "MCAR"
            justificacion = "La tasa de ausencia es homogénea entre fuentes, estaciones y meses."
        if col == "precipitacion_mm":
            justificacion += " Riesgo MNAR: los pluviómetros pueden fallar con lluvias extremas."
        filas.append({
            "variable": col,
            "nulos": int(faltantes.sum()),
            "porcentaje": round(float(faltantes.mean() * 100), 2),
            "variable_asociada": asociada,
            "mecanismo": mecanismo,
            "justificacion": justificacion,
            "imputacion": ESTRATEGIA_IMPUTACION.get(col, "mediana mensual"),
        })
    return pd.DataFrame(filas, columns=["variable", "nulos", "porcentaje", "variable_asociada",
                                        "mecanismo", "justificacion", "imputacion"])


def inferir_mecanismo_ausencia(df: pd.DataFrame) -> str:
    """Resumen textual del diagnóstico de ausencia para el reporte de ejecución."""
    diagnostico = diagnosticar_mecanismo_por_variable(df)
    if diagnostico.empty:
        return "No se encontraron valores faltantes en las variables medidas."
    partes = [f"{r.variable}: {r.mecanismo} ({r.justificacion})" for r in diagnostico.itertuples()]
    return " | ".join(partes)


# Justificación de cada estrategia de imputación:
# - Temperaturas, humedad y viento siguen un ciclo estacional fuerte; la mediana del mismo mes
#   y estación conserva ese ciclo y es robusta a atípicos. Si la estación no tiene datos ese mes
#   (ausencia MAR por fuente), se usa la mediana del mes en todas las estaciones.
# - Precipitación: distribución muy sesgada (la mayoría de días = 0); la mediana mensual evita
#   inventar lluvia en temporada seca.
ESTRATEGIA_IMPUTACION = {
    "temperatura_maxima": "mediana por estación y mes; respaldo: mediana del mes",
    "temperatura_minima": "mediana por estación y mes; respaldo: mediana del mes",
    "temperatura_media": "promedio de máxima y mínima del mismo día; respaldo: mediana del mes",
    "precipitacion_mm": "mediana del mes (distribución sesgada)",
    "humedad_relativa": "mediana por estación y mes; respaldo: mediana del mes",
    "velocidad_viento_kmh": "mediana por estación y mes; respaldo: mediana del mes",
    "rafagas_viento_kmh": "mediana por estación y mes; respaldo: mediana del mes",
}


def imputar_faltantes(df: pd.DataFrame) -> pd.DataFrame:
    """Imputa faltantes según ESTRATEGIA_IMPUTACION y marca cada valor imputado en `<col>_imputado`."""
    datos = df.copy()
    if "mes" not in datos.columns and "fecha" in datos.columns:
        datos["mes"] = pd.to_datetime(datos["fecha"]).dt.month
    grupo_mes = datos["mes"] if "mes" in datos.columns else pd.Series(0, index=datos.index)
    grupo_est = [datos["estacion_id"], grupo_mes] if "estacion_id" in datos.columns else [grupo_mes]

    for col in VARIABLES_CONTINUAS:
        if col not in datos.columns:
            continue
        datos[f"{col}_imputado"] = datos[col].isna().astype(int)
        if col == "temperatura_media" and {"temperatura_maxima", "temperatura_minima"}.issubset(datos.columns):
            datos[col] = datos[col].fillna((datos["temperatura_maxima"] + datos["temperatura_minima"]) / 2)
        elif col != "precipitacion_mm":
            datos[col] = datos[col].fillna(datos[col].groupby(grupo_est).transform("median"))
        datos[col] = datos[col].fillna(datos[col].groupby(grupo_mes).transform("median"))
        datos[col] = datos[col].fillna(datos[col].median())
    return datos


def _limites_iqr(serie: pd.Series) -> tuple[float, float]:
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def detectar_atipicos(df: pd.DataFrame, columnas: list[str] | None = None) -> pd.DataFrame:
    """Detecta atípicos con IQR y Z-Score robusto (MAD) y los trata por winsorización.

    - `<col>_atipico`: True si el valor queda fuera de las cercas de Tukey (IQR) **o**
      su Z-Score robusto |0.6745·(x - mediana) / MAD| supera 3.5.
    - `<col>_tratado`: valor recortado a las cercas IQR (winsorización). La columna original
      se conserva intacta para trazabilidad; normalización y análisis usan la tratada.
    - Precipitación: como la mayoría de días valen 0, el IQR global es 0 y marcaría toda lluvia
      como atípica. Por eso las cercas se calculan sólo con días lluviosos y sólo se recorta
      el extremo superior.
    """
    datos = df.copy()
    for col in columnas or VARIABLES_CONTINUAS:
        if col not in datos.columns:
            continue
        serie = datos[col].astype(float)
        referencia = serie[serie > 0] if col == "precipitacion_mm" else serie
        referencia = referencia.dropna()
        if referencia.empty:
            datos[f"{col}_atipico"] = False
            datos[f"{col}_tratado"] = serie
            continue

        inferior, superior = _limites_iqr(referencia)
        mediana = referencia.median()
        mad = (referencia - mediana).abs().median()
        z_robusto = 0.6745 * (serie - mediana) / mad if mad else pd.Series(0.0, index=serie.index)

        if col == "precipitacion_mm":
            inferior = 0.0
            atipico = (serie > superior) | ((serie > 0) & (z_robusto.abs() > 3.5))
        else:
            atipico = (serie < inferior) | (serie > superior) | (z_robusto.abs() > 3.5)

        datos[f"{col}_zscore_robusto"] = z_robusto.round(3)
        datos[f"{col}_atipico"] = atipico.fillna(False)
        datos[f"{col}_tratado"] = serie.clip(lower=inferior, upper=superior)
    return datos


def normalizar_variables(df: pd.DataFrame, columnas: list[str] | None = None) -> pd.DataFrame:
    """Crea columnas adicionales para Min-Max y Z-score sin perder las originales.

    Si existe `<col>_tratado` (salida de detectar_atipicos), se normaliza esa versión para que
    los atípicos no compriman la escala Min-Max.
    """
    datos = df.copy()
    for col in columnas or VARIABLES_CONTINUAS:
        if col not in datos.columns:
            continue
        base = datos[f"{col}_tratado"] if f"{col}_tratado" in datos.columns else datos[col]
        min_v = base.min()
        max_v = base.max()
        rango = max_v - min_v
        if rango != 0:
            datos[f"{col}_minmax"] = (base - min_v) / rango
        else:
            datos[f"{col}_minmax"] = 0.0
        media = base.mean()
        std = base.std(ddof=0)
        if std != 0:
            datos[f"{col}_zscore"] = (base - media) / std
        else:
            datos[f"{col}_zscore"] = 0.0
    return datos
