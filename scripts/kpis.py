"""KPIs (IE5 / IE8): cálculo de los indicadores clave, semáforo frente a la meta e historial.

K1 Publicaciones del día sin reacción (%)        -> P1 operacional
K2 Interacciones por publicación del último mes  -> P2 táctica
K3 Participación de Móvil en los registros (%)   -> P3 estratégica
K4 Cumplimiento promedio de la meta de likes (%) -> impacto de campañas
K5 Usuarios activos (%)                          -> participación y retención
"""
import json
from datetime import datetime

import pandas as pd

from common import DIR_PROCESADOS, ROOT


def _semaforo(valor, meta, sentido, tol):
    if valor is None or pd.isna(valor):
        return "Sin datos"
    ok = valor <= meta if sentido == "menor" else valor >= meta
    if ok:
        return "Verde"
    cerca = valor <= meta + tol if sentido == "menor" else valor >= meta - tol
    return "Amarillo" if cerca else "Rojo"


def calcular_kpis(t: dict, ctx: dict) -> pd.DataFrame:
    metas = json.loads((ROOT / "config" / "metas_kpi.json").read_text(encoding="utf-8"))
    p, u, r3, c = t["fact_publicaciones"], t["dim_usuarios"], t["p3_registros_dispositivo"], t["campanas"]
    dia, mes, anio = ctx["dia_ref"], ctx["mes_ref"], ctx["anio_ref"]
    filas = []

    def add(clave, nombre, nivel, valor, unidad, formula, fuente, detalle, valor_anterior=None):
        m = metas[clave]
        filas.append({"kpi": clave.split("_")[0], "nombre": nombre, "nivel": nivel, "valor": valor, "unidad": unidad,
                      "valor_anterior": valor_anterior,
                      "variacion": None if valor_anterior is None or valor is None else round(valor - valor_anterior, 2),
                      "meta": m["meta"], "sentido": m["sentido"],
                      "estado": _semaforo(valor, m["meta"], m["sentido"], m["tolerancia"]),
                      "formula": formula, "fuente": fuente, "detalle": detalle})

    # K1 · operacional
    hoy = p[p["fecha_dia"] == dia]
    ayer = p[p["fecha_dia"] == dia - pd.Timedelta(days=1)]
    k1 = round(hoy["sin_reaccion"].mean() * 100, 1) if len(hoy) else None
    k1a = round(ayer["sin_reaccion"].mean() * 100, 1) if len(ayer) else None
    add("K1_sin_reaccion_dia_pct", "Publicaciones del día sin reacción", "Operacional", k1, "%",
        "publicaciones del día con 0 reacciones ÷ publicaciones del día × 100",
        "publicaciones + reacciones ($lookup)",
        f"Día {dia:%d-%m-%Y}: {int(hoy['sin_reaccion'].sum())} de {len(hoy)} publicaciones sin reacción", k1a)

    # K2 · táctico
    pm = p[p["mes"] == mes]
    previos = sorted(m for m in p["mes"].unique() if m < mes)
    mes_ant = previos[-1] if previos else mes
    pa = p[p["mes"] == mes_ant]
    k2 = round(pm["interacciones"].mean(), 2) if len(pm) else None
    k2a = round(pa["interacciones"].mean(), 2) if len(pa) else None
    g = t["p2_categoria_mes"]
    lider = g[(g["mes"] == mes) & (g["ranking_mes"] == 1)]
    add("K2_interacciones_por_pub_mes", "Interacciones por publicación (último mes cerrado)", "Táctico", k2, "int/pub",
        "(reacciones + comentarios) ÷ publicaciones del mes",
        "publicaciones + reacciones + comentarios ($lookup)",
        f"Mes {mes}; categoría líder: {', '.join(lider['categoria'])}" if len(lider) else f"Mes {mes}", k2a)

    # K3 · estratégico
    def share(a):
        f = r3[(r3["anio"] == a) & (r3["dispositivo"] == "Móvil")]
        return float(f["participacion_pct"].iloc[0]) if len(f) else None
    anio_k3 = anio if (r3["anio"] == anio).any() else int(r3["anio"].max())
    add("K3_participacion_movil_pct", "Participación de Móvil en nuevos registros", "Estratégico", share(anio_k3), "%",
        "registros con dispositivo Móvil del año ÷ registros del año × 100", "usuarios ($group por año y dispositivo)",
        f"Año {anio_k3} (período {r3.loc[r3['anio'] == anio_k3, 'periodo'].iloc[0]}) frente a {anio_k3 - 1}",
        share(anio_k3 - 1))

    # K4 · campañas
    k4 = round(c["cumplimiento_likes_pct"].mean(), 2) if len(c) else None
    add("K4_cumplimiento_campanas_pct", "Cumplimiento promedio de la meta de likes", "Táctico", k4, "%",
        "promedio de (likes reales ÷ meta de likes × 100) por campaña",
        "campañas ($unwind publicaciones_asociadas) + reacciones 'Me gusta'",
        f"{len(c)} campañas; {int((c['cumplimiento_likes_pct'] >= 1).sum())} superan el 1 % de su meta")

    # K5 · participación
    k5 = round((u["total_actividad"] > 0).mean() * 100, 1) if len(u) else None
    add("K5_usuarios_activos_pct", "Usuarios activos", "Táctico", k5, "%",
        "usuarios con al menos 1 publicación, reacción o comentario ÷ usuarios × 100",
        "usuarios + publicaciones + reacciones + comentarios ($unionWith)",
        f"{int((u['nivel_actividad'] == 'Alto').sum())} usuarios con actividad alta (5+ acciones)")

    df = pd.DataFrame(filas)
    df.insert(0, "fecha_ejecucion", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    df.insert(1, "dia_referencia", f"{dia:%Y-%m-%d}")
    return df


def guardar_historial(kpis: pd.DataFrame) -> pd.DataFrame:
    """Agrega la ejecución al historial para ver la evolución de cada KPI en el tiempo."""
    ruta = DIR_PROCESADOS / "kpis_historial.csv"
    cols = ["fecha_ejecucion", "dia_referencia", "kpi", "nombre", "valor", "meta", "estado"]
    hist = pd.read_csv(ruta) if ruta.exists() else pd.DataFrame(columns=cols)
    hist = pd.concat([hist, kpis[cols]], ignore_index=True)
    hist.to_csv(ruta, index=False, encoding="utf-8-sig")
    return hist
