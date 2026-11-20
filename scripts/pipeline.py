"""PIPELINE ETL COMPLETO: MongoDB Atlas -> transformación -> tablas para Power BI -> KPIs -> reporte.

Uso:
    python scripts/pipeline.py                       # lee desde Atlas (modo normal)
    python scripts/pipeline.py --offline             # usa los JSON de data/anexo (pruebas sin conexión)
    python scripts/pipeline.py --fecha-ref 2025-07-13  # fija el "día de hoy" del análisis

Salidas (se sobrescriben en cada ejecución, Power BI las relee con "Actualizar"):
    data/processed/*.csv y data/processed/contentflow_ep3.xlsx   -> modelo de Power BI
    data/processed/kpis_historial.csv                            -> evolución de los KPIs
    reportes/reporte_kpis.html                                   -> reporte automático
    docs/transformaciones.csv                                    -> documentación de transformaciones
    logs/pipeline.log                                            -> trazabilidad
"""
import argparse
import time
from datetime import datetime

import pandas as pd

import extraccion as ex
from common import DIR_DOCS, DIR_PROCESADOS, get_db, get_logger
from kpis import calcular_kpis, guardar_historial
from reporte import generar_reporte
from transformacion import transformar


def ejecutar(offline: bool = False, fecha_ref: datetime | None = None, guardar: bool = True):
    log = get_logger("pipeline")
    t0 = time.perf_counter()
    log.info("=== Inicio del pipeline (%s) ===", "offline" if offline else "Atlas")

    # 1. EXTRACCIÓN
    if offline:
        raw = ex.extraer_offline(log)
        fuente = "JSON del anexo (modo offline)"
    else:
        client, db = get_db(log)
        raw = ex.extraer_atlas(db, log)
        fuente = "MongoDB Atlas · Cluster0 · base ContentFlow"
    if fecha_ref is None:
        fecha_ref = pd.to_datetime(raw["publicaciones"]["fecha"]).max()
    dia = pd.Timestamp(fecha_ref).normalize().to_pydatetime()
    raw["sin_reaccion_dia"] = ex.sin_reaccion_offline(raw["publicaciones"], dia) if offline else ex.sin_reaccion_atlas(db, dia)
    log.info("Día de referencia: %s · publicaciones sin reacción ese día: %d", f"{dia:%Y-%m-%d}", len(raw["sin_reaccion_dia"]))
    if not offline:
        client.close()

    # 2. TRANSFORMACIÓN
    tablas, registro, ctx = transformar(raw, dia)
    for nombre, df in tablas.items():
        log.info("Tabla %-26s %5d filas × %2d columnas", nombre, *df.shape)

    # 3. KPIs
    kpis = calcular_kpis(tablas, ctx)
    for _, k in kpis.iterrows():
        log.info("%s %-50s %s %s (%s)", k["kpi"], k["nombre"], k["valor"], k["unidad"], k["estado"])
    tablas["kpis"] = kpis.drop(columns=["fecha_ejecucion"])

    if guardar:
        # 4. CARGA: archivos que lee Power BI
        for nombre, df in tablas.items():
            df.to_csv(DIR_PROCESADOS / f"{nombre}.csv", index=False, encoding="utf-8-sig")
        with pd.ExcelWriter(DIR_PROCESADOS / "contentflow_ep3.xlsx") as xl:
            for nombre, df in tablas.items():
                df.to_excel(xl, sheet_name=nombre[:31], index=False)
            pd.DataFrame([{"fecha_ejecucion": datetime.now(), "fuente": fuente, "dia_referencia": ctx["dia_ref"],
                           "mes_referencia": ctx["mes_ref"], "anio_referencia": ctx["anio_ref"]}]).to_excel(
                xl, sheet_name="actualizacion", index=False)
        guardar_historial(kpis)
        registro.to_csv(DIR_DOCS / "transformaciones.csv", index=False, encoding="utf-8-sig")
        raw["_metricas_extraccion"].to_csv(DIR_DOCS / "consultas_extraccion.csv", index=False, encoding="utf-8-sig")
        # 5. REPORTE AUTOMÁTICO
        ruta = generar_reporte(tablas, kpis, ctx, fuente)
        log.info("Reporte generado: %s", ruta)

    log.info("=== Pipeline terminado en %.1f s ===", time.perf_counter() - t0)
    return tablas, registro, ctx


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Pipeline ETL ContentFlow EP3")
    ap.add_argument("--offline", action="store_true", help="usar los JSON de data/anexo en vez de Atlas")
    ap.add_argument("--fecha-ref", help="día de referencia AAAA-MM-DD (por defecto, la última publicación)")
    a = ap.parse_args()
    ejecutar(offline=a.offline, fecha_ref=datetime.fromisoformat(a.fecha_ref) if a.fecha_ref else None)
