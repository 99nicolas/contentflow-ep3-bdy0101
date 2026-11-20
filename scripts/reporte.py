"""REPORTE AUTOMÁTICO (IE8): genera reportes/reporte_kpis.html en cada ejecución del pipeline.

Es un HTML autocontenido (sin dependencias externas) que se puede abrir en cualquier navegador,
adjuntar a un correo o imprimir a PDF. Destaca los KPIs con semáforo y responde las 3 preguntas.
"""
import html
from datetime import datetime

import pandas as pd

from common import DIR_REPORTES

COLOR = {"Verde": "#1E7A52", "Amarillo": "#B7791F", "Rojo": "#B42318", "Sin datos": "#6B7280"}


def _num(v, dec=1):
    if v is None or pd.isna(v):
        return "—"
    s = f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _tabla(df: pd.DataFrame, barras: str | None = None, maximo: float | None = None) -> str:
    if df.empty:
        return "<p class='vacio'>Sin registros para el período.</p>"
    cab = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    filas = []
    for _, fila in df.iterrows():
        celdas = []
        for col, v in fila.items():
            txt = _num(v, 2 if isinstance(v, float) else 0) if isinstance(v, (int, float)) and not isinstance(v, bool) else html.escape(str(v))
            if barras and col == barras and maximo:
                ancho = max(2, min(100, float(v) / maximo * 100))
                txt = f"<div class='barra'><span style='width:{ancho:.0f}%'></span><b>{txt}</b></div>"
            celdas.append(f"<td>{txt}</td>")
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    return f"<table><thead><tr>{cab}</tr></thead><tbody>{''.join(filas)}</tbody></table>"


def generar_reporte(t: dict, kpis: pd.DataFrame, ctx: dict, fuente: str) -> str:
    tarjetas = []
    for _, k in kpis.iterrows():
        dec = 2 if k["unidad"] == "int/pub" or k["kpi"] == "K4" else 1
        var = ""
        if k["variacion"] is not None and not pd.isna(k["variacion"]):
            signo = "+" if k["variacion"] > 0 else ""
            var = f"<span class='var'>{signo}{_num(k['variacion'], dec)} vs período anterior</span>"
        tarjetas.append(f"""
        <div class='kpi' style='border-top-color:{COLOR[k['estado']]}'>
          <div class='kpi-id'>{k['kpi']} · {html.escape(k['nivel'])}</div>
          <div class='kpi-nombre'>{html.escape(k['nombre'])}</div>
          <div class='kpi-valor'>{_num(k['valor'], dec)} <small>{html.escape(k['unidad'])}</small></div>
          <div class='kpi-meta'><span class='dot' style='background:{COLOR[k['estado']]}'></span>{k['estado']} · meta {'≤' if k['sentido'] == 'menor' else '≥'} {_num(k['meta'], dec)}</div>
          {var}
          <div class='kpi-det'>{html.escape(str(k['detalle']))}</div>
        </div>""")

    p1 = t["p1_sin_reaccion_dia"].copy()
    p1["fecha"] = p1["fecha"].dt.strftime("%d-%m-%Y")
    p1["horas_sin_reaccion"] = p1["horas_sin_reaccion"].map(lambda v: _num(v, 1))
    p1 = p1.rename(columns={"publicacion_id": "Publicación", "fecha": "Fecha", "hora": "Hora", "categoria": "Categoría",
                            "tipo": "Tipo", "horas_sin_reaccion": "Horas sin reacción"})

    g = t["p2_categoria_mes"]
    p2 = g[g["mes"] == ctx["mes_ref"]][["ranking_mes", "categoria", "publicaciones", "interacciones", "interacciones_por_pub"]]
    p2 = p2.rename(columns={"ranking_mes": "#", "categoria": "Categoría", "publicaciones": "Publicaciones",
                            "interacciones": "Interacciones", "interacciones_por_pub": "Interacciones por publicación"})

    r3 = t["p3_registros_dispositivo"].pivot_table(index=["anio", "periodo"], columns="dispositivo",
                                                   values="participacion_pct").reset_index()
    r3.columns = [str(c) for c in r3.columns]
    r3 = r3.rename(columns={"anio": "Año", "periodo": "Período"})
    r3["Año"] = r3["Año"].astype(int).astype(str)
    for col in r3.columns[2:]:
        r3[col] = r3[col].map(lambda v: f"{_num(v)} %")

    c = t["campanas"].sort_values("cumplimiento_likes_pct", ascending=False)
    camp = pd.concat([c.head(5), c.tail(5)])[["campana_id", "nombre", "objetivo", "meta_likes", "likes_reales",
                                              "cumplimiento_likes_pct"]]
    camp = camp.rename(columns={"campana_id": "Campaña", "nombre": "Nombre", "objetivo": "Objetivo", "meta_likes": "Meta likes",
                                "likes_reales": "Likes reales", "cumplimiento_likes_pct": "Cumplimiento %"})

    top = t["dim_usuarios"].sort_values(["total_actividad", "usuario_id"], ascending=[False, True]).head(10)
    top = top[["usuario_id", "dispositivo", "publicaciones", "reacciones", "comentarios", "total_actividad"]].rename(
        columns={"usuario_id": "Usuario", "dispositivo": "Dispositivo", "publicaciones": "Publicaciones",
                 "reacciones": "Reacciones", "comentarios": "Comentarios", "total_actividad": "Total"})

    contenido = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ContentFlow · Reporte de KPIs</title>
<style>
:root {{ --tinta:#14232D; --suave:#4A5A63; --linea:#DDE2DE; --fondo:#F6F7F4; --verde:#1E7A52; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family: 'Segoe UI', Arial, sans-serif; color:var(--tinta); background:var(--fondo); }}
header {{ background:#0F1F2A; color:#F3F4EF; padding:28px 40px; }}
header h1 {{ margin:0 0 6px; font-size:26px; }}
header p {{ margin:0; color:#BFD0CC; font-size:14px; }}
main {{ padding:28px 40px; max-width:1200px; margin:auto; }}
h2 {{ font-size:18px; margin:32px 0 6px; }}
.preg {{ color:var(--suave); margin:0 0 12px; font-size:14px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; }}
.kpi {{ background:#fff; border:1px solid var(--linea); border-top:6px solid; border-radius:10px; padding:16px; }}
.kpi-id {{ font-size:12px; color:var(--suave); letter-spacing:.5px; text-transform:uppercase; }}
.kpi-nombre {{ font-weight:600; margin:4px 0 8px; min-height:40px; }}
.kpi-valor {{ font-size:30px; font-weight:700; }}
.kpi-valor small {{ font-size:14px; color:var(--suave); font-weight:400; }}
.kpi-meta {{ font-size:13px; margin-top:6px; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }}
.var {{ display:block; font-size:12px; color:var(--suave); margin-top:4px; }}
.kpi-det {{ font-size:12px; color:var(--suave); margin-top:8px; border-top:1px solid var(--linea); padding-top:8px; }}
table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--linea); font-size:14px; }}
th {{ background:#E8EEF0; text-align:left; padding:8px 10px; }}
td {{ padding:7px 10px; border-top:1px solid var(--linea); }}
.barra {{ position:relative; background:#EEF2EF; border-radius:4px; height:22px; }}
.barra span {{ position:absolute; left:0; top:0; bottom:0; background:#9FD3B8; border-radius:4px; }}
.barra b {{ position:relative; padding-left:6px; line-height:22px; font-weight:600; }}
.dos {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
.vacio {{ color:var(--suave); font-style:italic; }}
footer {{ color:var(--suave); font-size:12px; padding:24px 40px 40px; max-width:1200px; margin:auto; }}
@media (max-width: 800px) {{ .dos {{ grid-template-columns:1fr; }} main, header, footer {{ padding-left:16px; padding-right:16px; }} }}
</style></head><body>
<header>
  <h1>ContentFlow · Reporte automático de KPIs</h1>
  <p>Generado el {datetime.now():%d-%m-%Y a las %H:%M} · Fuente: {html.escape(fuente)} · Día de referencia {ctx['dia_ref']:%d-%m-%Y} · Mes cerrado {ctx['mes_ref']}</p>
</header>
<main>
  <section class="kpis">{''.join(tarjetas)}</section>

  <h2>P1 · Operacional: publicaciones del día sin reacciones</h2>
  <p class="preg">¿Qué publicaciones del {ctx['dia_ref']:%d-%m-%Y} todavía no reciben ninguna reacción? Acción: impulsarlas o revisarlas hoy.</p>
  {_tabla(p1)}

  <h2>P2 · Táctica: interacciones por publicación según categoría ({ctx['mes_ref']})</h2>
  <p class="preg">¿Qué categoría genera más interacciones por publicación en el último mes cerrado? Acción: ajustar el plan editorial del mes siguiente.</p>
  {_tabla(p2, barras="Interacciones por publicación", maximo=float(p2["Interacciones por publicación"].max() or 1) if not p2.empty else None)}

  <h2>P3 · Estratégica: participación de cada dispositivo en los registros nuevos</h2>
  <p class="preg">¿Qué dispositivo crece más entre los usuarios nuevos año a año? Se comparan porcentajes porque 2023 y 2025 son años parciales.</p>
  {_tabla(r3)}

  <div class="dos">
    <div><h2>Campañas: mejor y peor cumplimiento de likes</h2>{_tabla(camp)}</div>
    <div><h2>Usuarios más activos</h2>{_tabla(top)}</div>
  </div>
</main>
<footer>Reporte generado por scripts/pipeline.py (extracción desde MongoDB → transformación con pandas → KPIs). Se actualiza en cada ejecución programada; el historial de KPIs queda en data/processed/kpis_historial.csv.</footer>
</body></html>"""
    ruta = DIR_REPORTES / "reporte_kpis.html"
    ruta.write_text(contenido, encoding="utf-8")
    return str(ruta)
