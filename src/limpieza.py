from __future__ import annotations

import pandas as pd


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
        return (
            df.groupby(["mes", "municipio"])
            .apply(lambda g: g.isna().sum())
            .reset_index()
        )
    return pd.DataFrame({"mensaje": ["No se detectaron columnas para identificar patrones temporales."]})


def inferir_mecanismo_ausencia(df: pd.DataFrame) -> str:
    """Retorna una clasificación conservadora basada en la evidencia disponible."""
    missing = df.isna().mean()
    if missing.max() > 0.30:
        return "Mecanismo de ausencia potencialmente MAR/MNAR: la falta de datos parece no aleatoria y requiere inspección contextual."
    if missing.max() > 0.05:
        return "Se observa un patrón de ausencia compatible con MAR, pero no es posible afirmarlo con certeza sin información contextual."
    return "No hay evidencia suficiente para afirmar MCAR; la ausencia puede ser aleatoria, pero no se puede concluir estadísticamente sin variables de contexto."


def imputar_faltantes(df: pd.DataFrame) -> pd.DataFrame:
    """Imputa valores faltantes con estrategias meteorológicamente razonables."""
    datos = df.copy()
    for col in [
        "temperatura_maxima",
        "temperatura_minima",
        "temperatura_media",
        "precipitacion_mm",
        "humedad_relativa",
        "velocidad_viento_kmh",
        "rafagas_viento_kmh",
    ]:
        if col not in datos.columns:
            continue
        datos[f"{col}_imputado"] = datos[col].isna().astype(int)
        if col == "precipitacion_mm":
            mediana = datos.groupby("mes")[col].transform("median")
            datos[col] = datos[col].fillna(mediana)
        else:
            mediana = datos[col].median()
            datos[col] = datos[col].fillna(mediana)
    return datos


def detectar_atipicos(df: pd.DataFrame, columnas: list[str] | None = None) -> pd.DataFrame:
    """Aplica criterio IQR para detectar valores estadísticamente extremos."""
    datos = df.copy()
    if columnas is None:
        columnas = [
            "temperatura_maxima",
            "temperatura_minima",
            "temperatura_media",
            "precipitacion_mm",
            "humedad_relativa",
            "velocidad_viento_kmh",
            "rafagas_viento_kmh",
        ]
    for col in columnas:
        if col not in datos.columns:
            continue
        q1 = datos[col].quantile(0.25)
        q3 = datos[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        datos[f"{col}_atipico"] = (datos[col] < lower) | (datos[col] > upper)
    return datos


def normalizar_variables(df: pd.DataFrame, columnas: list[str] | None = None) -> pd.DataFrame:
    """Crea columnas adicionales para Min-Max y Z-score sin perder las originales."""
    datos = df.copy()
    if columnas is None:
        columnas = [
            "temperatura_maxima",
            "temperatura_minima",
            "temperatura_media",
            "precipitacion_mm",
            "humedad_relativa",
            "velocidad_viento_kmh",
            "rafagas_viento_kmh",
        ]
    for col in columnas:
        if col not in datos.columns:
            continue
        min_v = datos[col].min()
        max_v = datos[col].max()
        rango = max_v - min_v
        if rango != 0:
            datos[f"{col}_minmax"] = (datos[col] - min_v) / rango
        else:
            datos[f"{col}_minmax"] = 0.0
        media = datos[col].mean()
        std = datos[col].std(ddof=0)
        if std != 0:
            datos[f"{col}_zscore"] = (datos[col] - media) / std
        else:
            datos[f"{col}_zscore"] = 0.0
    return datos
