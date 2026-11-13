from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indicadores import generar_agregados_mensuales
from src.ingestion import cargar_datos_bronze
from src.integracion import homologar_columnas, integrar_fuentes, normalizar_unidades
from src.limpieza import (diagnosticar_faltantes, detectar_atipicos, identificar_patrones_ausencia,
                          imputar_faltantes, inferir_mecanismo_ausencia, normalizar_variables)
from src.transformaciones import agregar_jerarquias_geograficas, agregar_jerarquias_temporales, discretizar_eventos
from src.validacion import ejecutar_puerta_calidad


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    datos = homologar_columnas(df.copy())
    datos = normalizar_unidades(datos)
    datos = agregar_jerarquias_geograficas(datos)
    datos = agregar_jerarquias_temporales(datos)
    datos = discretizar_eventos(datos)
    return datos


def run_pipeline(project_root: str | Path, source_path: str | Path | None = None) -> dict:
    """Ejecuta el flujo completo Bronce -> Plata -> Oro con cuarentena."""
    root = Path(project_root)
    bronze_dir = root / "data" / "bronze"
    silver_dir = root / "data" / "silver"
    gold_dir = root / "data" / "gold"
    quarantine_dir = root / "data" / "quarantine"
    for directory in (bronze_dir, silver_dir, gold_dir, quarantine_dir):
        directory.mkdir(parents=True, exist_ok=True)

    if source_path is not None:
        raw_df = pd.read_csv(source_path, parse_dates=["fecha", "fecha_extraccion"])
    else:
        raw_df = cargar_datos_bronze(root)

    bronze_path = bronze_dir / "weather_bronze.csv"
    raw_df.to_csv(bronze_path, index=False)

    df = _prepare_df(raw_df)
    report_missing = diagnosticar_faltantes(df)
    patrones = identificar_patrones_ausencia(df)
    mecanismo = inferir_mecanismo_ausencia(df)
    df = imputar_faltantes(df)
    df = detectar_atipicos(df)
    df = normalizar_variables(df, [
        "temperatura_maxima",
        "temperatura_minima",
        "temperatura_media",
        "precipitacion_mm",
        "humedad_relativa",
        "velocidad_viento_kmh",
        "rafagas_viento_kmh",
    ])

    validos, invalidos, reporte = ejecutar_puerta_calidad(df, quarantine_dir)
    silver_path = silver_dir / "weather_silver.csv"
    validos.to_csv(silver_path, index=False)
    invalidos.to_csv(quarantine_dir / "weather_quarantine.csv", index=False)

    gold_df = generar_agregados_mensuales(validos)
    gold_path = gold_dir / "weather_gold.csv"
    gold_df.to_csv(gold_path, index=False)

    report = {
        "arquitectura": "Medallion",
        "bronze_path": str(bronze_path),
        "silver_path": str(silver_path),
        "gold_path": str(gold_path),
        "quarantine_path": str(quarantine_dir / "weather_quarantine.csv"),
        "missing_report": report_missing.to_dict(),
        "patrones_ausencia": patrones.to_dict(orient="records"),
        "mecanismo_ausencia": mecanismo,
        "reporte_calidad": reporte,
    }
    with (root / "data" / "execution_report.json").open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)

    return report


if __name__ == "__main__":
    run_pipeline(Path(__file__).resolve().parent.parent)
