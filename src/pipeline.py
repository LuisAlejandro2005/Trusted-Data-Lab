from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indicadores import generar_agregados_mensuales, seleccionar_variables
from src.ingestion import cargar_datos_bronze, cargar_fuente_secundaria
from src.integracion import homologar_columnas, integrar_fuentes, preparar_fuente_conagua
from src.limpieza import (VARIABLES_CONTINUAS, detectar_atipicos, diagnosticar_faltantes,
                          diagnosticar_mecanismo_por_variable, identificar_patrones_ausencia,
                          imputar_faltantes, inferir_mecanismo_ausencia, normalizar_variables)
from src.transformaciones import (agregar_jerarquias_geograficas, agregar_jerarquias_temporales,
                                  discretizar_eventos, discretizar_variables)
from src.validacion import ejecutar_puerta_calidad


def run_pipeline(project_root: str | Path, source_path: str | Path | None = None) -> dict:
    """Ejecuta el flujo Bronce -> Integración -> Puerta de calidad -> Plata -> Oro.

    Orden de etapas:
    1. Bronce: se guardan ambas fuentes crudas tal como llegan.
    2. Integración: homologación de esquema, tipos, unidades y catálogos; fusión con
       resolución de conflictos.
    3. Puerta de calidad (Pandera): los inválidos van a cuarentena con su motivo.
       Va antes de la limpieza para que los valores imposibles no sesguen medianas ni escalas.
    4. Limpieza en Plata: diagnóstico de ausencia, imputación, atípicos, normalización,
       jerarquías y discretización.
    5. Oro: reducción por agregación mensual y por selección de variables.
    """
    root = Path(project_root)
    bronze_dir = root / "data" / "bronze"
    silver_dir = root / "data" / "silver"
    gold_dir = root / "data" / "gold"
    quarantine_dir = root / "data" / "quarantine"
    for directory in (bronze_dir, silver_dir, gold_dir, quarantine_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # 1. Bronce
    if source_path is not None:
        fuente_a = pd.read_csv(source_path, parse_dates=["fecha", "fecha_extraccion"])
    else:
        fuente_a = cargar_datos_bronze(root)
    fuente_b = cargar_fuente_secundaria(root)
    bronze_path = bronze_dir / "weather_bronze.csv"
    fuente_a.to_csv(bronze_path, index=False)

    # 2. Integración
    integrado = integrar_fuentes(homologar_columnas(fuente_a), preparar_fuente_conagua(fuente_b))
    resumen_integracion = {
        "registros_fuente_a": int(len(fuente_a)),
        "registros_fuente_b": int(len(fuente_b)),
        "registros_integrados": int(len(integrado)),
        "registros_con_conflicto": int((integrado["n_conflictos"] > 0).sum()),
        "registros_por_fuente": {str(k): int(v) for k, v in integrado["fuente_datos"].value_counts().items()},
    }

    # 3. Puerta de calidad
    validos, invalidos, reporte = ejecutar_puerta_calidad(integrado, quarantine_dir)

    # 4. Limpieza y preprocesamiento (capa Plata)
    df = agregar_jerarquias_temporales(validos)
    df = agregar_jerarquias_geograficas(df)
    report_missing = diagnosticar_faltantes(df)
    patrones = identificar_patrones_ausencia(df)
    diagnostico_ausencia = diagnosticar_mecanismo_por_variable(df)
    mecanismo = inferir_mecanismo_ausencia(df)
    df = imputar_faltantes(df)
    df = detectar_atipicos(df)
    df = normalizar_variables(df)
    df = discretizar_variables(df)
    df = discretizar_eventos(df)

    silver_path = silver_dir / "weather_silver.csv"
    df.to_csv(silver_path, index=False)
    diagnostico_ausencia.to_csv(silver_dir / "diagnostico_ausencia.csv", index=False)

    # 5. Oro: reducción de datos
    gold_df = generar_agregados_mensuales(df)
    gold_path = gold_dir / "weather_gold.csv"
    gold_df.to_csv(gold_path, index=False)

    analitico, resumen_seleccion = seleccionar_variables(df)
    analitico.to_csv(gold_dir / "weather_gold_analitico.csv", index=False)

    atipicos = {col: int(df[f"{col}_atipico"].sum()) for col in VARIABLES_CONTINUAS if f"{col}_atipico" in df.columns}

    report = {
        "arquitectura": "Medallion",
        "bronze_path": str(bronze_path),
        "silver_path": str(silver_path),
        "gold_path": str(gold_path),
        "quarantine_path": str(quarantine_dir / "weather_quarantine.csv"),
        "integracion": resumen_integracion,
        "reporte_calidad": reporte,
        "missing_report": report_missing.to_dict(),
        "patrones_ausencia": patrones.to_dict(orient="records"),
        "diagnostico_ausencia": diagnostico_ausencia.to_dict(orient="records"),
        "mecanismo_ausencia": mecanismo,
        "atipicos_detectados": atipicos,
        "reduccion": {
            "registros_plata": int(len(df)),
            "registros_oro_mensual": int(len(gold_df)),
            "seleccion_variables": resumen_seleccion,
        },
    }
    with (root / "data" / "execution_report.json").open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)

    return report


if __name__ == "__main__":
    resultado = run_pipeline(Path(__file__).resolve().parent.parent)
    calidad = resultado["reporte_calidad"]
    print(f"Integrados: {resultado['integracion']['registros_integrados']} | "
          f"válidos: {calidad['registros_validos']} | cuarentena: {calidad['registros_invalidos']} | "
          f"oro mensual: {resultado['reduccion']['registros_oro_mensual']}")
    print(f"Reporte completo: {Path(resultado['bronze_path']).parents[1] / 'execution_report.json'}")
