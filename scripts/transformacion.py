"""TRANSFORMACIÓN (IE2): deja los datos extraídos listos para Power BI.

Cada transformación queda registrada con su tipo (estructural, semántica, formato o limpieza),
lo que hace, cuántas filas tocó y por qué sirve a las preguntas del caso:
  P1 (operacional)  ¿Qué publicaciones del día todavía no reciben ninguna reacción?
  P2 (táctica)      ¿Qué categoría de contenido genera más interacciones por publicación cada mes?
  P3 (estratégica)  ¿Qué tipo de dispositivo crece más entre los usuarios nuevos, año a año?
El registro se exporta a docs/transformaciones.csv en cada ejecución.
"""
from datetime import datetime

import pandas as pd

MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun", 7: "jul", 8: "ago", 9: "sep", 10: "oct",
         11: "nov", 12: "dic"}
DISPOSITIVOS = {"desktop": "Escritorio", "escritorio": "Escritorio", "móvil": "Móvil", "movil": "Móvil",
                "mobile": "Móvil", "tablet": "Tablet"}


class Registro:
    """Acumula las transformaciones aplicadas para documentarlas automáticamente."""

    def __init__(self):
        self.filas = []

    def add(self, tipo, tabla, campo, operacion, antes, despues, justificacion, pregunta, afectadas):
        self.filas.append({"id": f"T{len(self.filas) + 1:02d}", "tipo": tipo, "tabla": tabla, "campo": campo,
                           "operacion": operacion, "antes": antes, "despues": despues,
                           "justificacion": justificacion, "pregunta": pregunta, "filas_afectadas": int(afectadas)})

    def df(self) -> pd.DataFrame:
        return pd.DataFrame(self.filas)


def _texto(s: pd.Series) -> pd.Series:
    """Quita espacios sobrantes y deja solo la primera letra en mayúscula (conserva tildes)."""
    return s.astype("string").str.strip().str.capitalize()


def _naive(s: pd.Series) -> pd.Series:
    """Fechas a datetime sin zona horaria (Power BI y Excel no aceptan zonas mezcladas)."""
    s = pd.to_datetime(s, errors="coerce")
    return s.dt.tz_localize(None) if s.dt.tz is not None else s


def transformar(raw: dict, fecha_ref: datetime | None = None):
    reg = Registro()
    out = {}

    # ------------------------------------------------------------------ publicaciones (P1 y P2)
    p = raw["publicaciones"].copy()
    n = len(p)
    p["fecha"] = _naive(p["fecha"])
    reg.add("Formato", "fact_publicaciones", "fecha_publicacion", "Conversión de tipo",
            "texto ISO o ISODate con zona", "datetime sin zona", "Permite filtrar por día (P1) y agrupar por mes (P2).",
            "P1, P2", n)
    sin_fecha = p["fecha"].isna().sum()
    p = p.dropna(subset=["fecha"])
    reg.add("Limpieza", "fact_publicaciones", "fecha", "Eliminar nulos", "fecha inválida o vacía",
            "fila descartada", "Una publicación sin fecha no se puede ubicar en el día ni en el mes.", "P1, P2", sin_fecha)

    p["fecha_dia"] = p["fecha"].dt.normalize()
    p["mes"] = p["fecha"].dt.strftime("%Y-%m")
    p["hora"] = p["fecha"].dt.hour
    reg.add("Formato", "fact_publicaciones", "fecha_dia, mes, hora", "Campos derivados de fecha",
            "2025-03-13 06:37:59", "2025-03-13 · 2025-03 · 6", "Día para P1, mes para P2 y hora para el horario de publicación.",
            "P1, P2", len(p))

    p["categoria"] = _texto(p["categoria"])
    p["tipo"] = _texto(p["tipo"])
    reg.add("Semántica", "fact_publicaciones", "categoria, tipo", "Normalización de texto",
            "' tecnología', 'VIDEO'", "'Tecnología', 'Video'", "Evita que una misma categoría aparezca dos veces en los gráficos.",
            "P2", len(p))

    for col in ("reacciones", "comentarios", "likes_comentarios"):
        p[col] = pd.to_numeric(p[col], errors="coerce").fillna(0).astype(int)
    reg.add("Estructural", "fact_publicaciones", "reacciones, comentarios", "Agregación de colecciones relacionadas",
            "documentos sueltos en reacciones y comentarios", "un conteo por publicación ($lookup + $count)",
            "Una fila por publicación con su interacción, sin duplicar filas en Power BI.", "P1, P2", len(p))

    p["interacciones"] = p["reacciones"] + p["comentarios"]
    p["sin_reaccion"] = (p["reacciones"] == 0).astype(int)
    reg.add("Semántica", "fact_publicaciones", "interacciones, sin_reaccion", "Campos derivados de negocio",
            "reacciones=0, comentarios=1", "interacciones=1, sin_reaccion=1",
            "Define qué es 'interacción' (P2) y marca las publicaciones que necesitan impulso (P1).", "P1, P2", len(p))
    out["fact_publicaciones"] = p[["publicacion_id", "usuario_id", "fecha", "fecha_dia", "mes", "hora", "categoria",
                                   "tipo", "reacciones", "comentarios", "likes_comentarios", "interacciones",
                                   "sin_reaccion"]].sort_values("fecha").reset_index(drop=True)

    if fecha_ref is None:
        fecha_ref = p["fecha"].max()
    dia_ref = pd.Timestamp(fecha_ref).normalize()
    meses_previos = sorted(m for m in p["mes"].unique() if m < dia_ref.strftime("%Y-%m"))
    mes_ref = meses_previos[-1] if meses_previos else dia_ref.strftime("%Y-%m")   # último mes cerrado con datos
    anio_ref = dia_ref.year

    # ------------------------------------------------------------------ P1: lista operacional del día
    sr = raw.get("sin_reaccion_dia")
    if sr is None or sr.empty:
        sr = pd.DataFrame(columns=["publicacion_id", "categoria", "tipo", "fecha"])
    sr = sr.copy()
    sr["fecha"] = _naive(sr["fecha"])
    sr["categoria"] = _texto(sr["categoria"])
    sr["tipo"] = _texto(sr["tipo"])
    sr["hora"] = sr["fecha"].dt.strftime("%H:%M")
    sr["horas_sin_reaccion"] = ((dia_ref + pd.Timedelta(days=1) - sr["fecha"]).dt.total_seconds() / 3600).round(1)
    reg.add("Semántica", "p1_sin_reaccion_dia", "horas_sin_reaccion", "Campo derivado",
            "fecha de publicación", "horas transcurridas hasta el cierre del día",
            "Prioriza en la lista las publicaciones que llevan más tiempo sin respuesta.", "P1", len(sr))
    out["p1_sin_reaccion_dia"] = sr[["publicacion_id", "fecha", "hora", "categoria", "tipo", "horas_sin_reaccion"]]

    # ------------------------------------------------------------------ P2: categoría por mes
    g = (out["fact_publicaciones"].groupby(["mes", "categoria"])
         .agg(publicaciones=("publicacion_id", "size"), interacciones=("interacciones", "sum")).reset_index())
    g["interacciones_por_pub"] = (g["interacciones"] / g["publicaciones"]).round(2)
    g["ranking_mes"] = g.groupby("mes")["interacciones_por_pub"].rank(ascending=False, method="min").astype(int)
    reg.add("Estructural", "p2_categoria_mes", "mes, categoria", "Agrupación y promedio",
            "500 publicaciones", f"{len(g)} filas (mes × categoría)",
            "Responde P2: compara categorías dentro de cada mes con un promedio, no con totales.", "P2", len(g))
    out["p2_categoria_mes"] = g.sort_values(["mes", "ranking_mes"]).reset_index(drop=True)

    # ------------------------------------------------------------------ usuarios (dimensión) y P3
    u = raw["usuarios"].copy()
    u["fecha_registro"] = _naive(u["fecha_registro"])
    u["anio_registro"] = u["fecha_registro"].dt.year
    reg.add("Formato", "dim_usuarios", "fecha_registro", "Conversión de tipo y año derivado",
            "texto ISO o ISODate", "datetime + anio_registro", "Agrupa los registros por año (P3).", "P3", len(u))

    antes = u["dispositivo"].astype(str).str.strip().str.lower()
    u["dispositivo"] = antes.map(DISPOSITIVOS).fillna(_texto(u["dispositivo"]))
    cambiados = int((antes == "desktop").sum())
    reg.add("Semántica", "dim_usuarios", "dispositivo", "Estandarización de valores",
            "'Desktop'", "'Escritorio'", "Unifica el idioma de las categorías del dashboard (Móvil, Escritorio, Tablet).",
            "P3", cambiados)
    u["genero"] = _texto(u["genero"])

    act = raw["actividad"].copy()
    u = u.merge(act, on="usuario_id", how="left")
    for col in ("publicaciones", "reacciones", "comentarios"):
        u[col] = u[col].fillna(0).astype(int)
    u["total_actividad"] = u[["publicaciones", "reacciones", "comentarios"]].sum(axis=1)
    reg.add("Estructural", "dim_usuarios", "publicaciones, reacciones, comentarios", "Unión de 3 colecciones ($unionWith)",
            "acciones en 3 colecciones", "un total de actividad por usuario",
            "Identifica a los usuarios más activos que pide la gerencia.", "Usuarios activos", len(u))
    u["nivel_actividad"] = pd.cut(u["total_actividad"], bins=[-1, 0, 2, 4, 10_000],
                                  labels=["Inactivo", "Bajo", "Medio", "Alto"]).astype(str)
    reg.add("Semántica", "dim_usuarios", "nivel_actividad", "Segmentación",
            "total_actividad = 5", "'Alto' (0 inactivo · 1-2 bajo · 3-4 medio · 5+ alto)",
            "Permite filtrar el dashboard por segmento de usuarios para estrategias de retención.", "Usuarios activos", len(u))
    out["dim_usuarios"] = u[["usuario_id", "genero", "dispositivo", "fecha_registro", "anio_registro", "publicaciones",
                             "reacciones", "comentarios", "total_actividad", "nivel_actividad"]]

    r3 = raw["registros_dispositivo"].copy()
    r3["dispositivo"] = r3["dispositivo"].astype(str).str.strip().str.lower().map(DISPOSITIVOS).fillna(r3["dispositivo"])
    r3 = r3.groupby(["anio", "dispositivo"], as_index=False)["registros"].sum()
    r3["participacion_pct"] = (r3["registros"] / r3.groupby("anio")["registros"].transform("sum") * 100).round(1)
    meses = u.groupby("anio_registro")["fecha_registro"].agg(["min", "max"])
    r3["periodo"] = r3["anio"].map(lambda a: f"{MESES[meses.loc[a, 'min'].month]}–{MESES[meses.loc[a, 'max'].month]}"
                                   if a in meses.index else "")
    r3["anio_completo"] = r3["anio"].map(lambda a: int(meses.loc[a, "min"].month == 1 and meses.loc[a, "max"].month == 12)
                                         if a in meses.index else 0)
    reg.add("Estructural", "p3_registros_dispositivo", "participacion_pct", "Porcentaje dentro de cada año",
            "registros por año y dispositivo", "participación % del año",
            "2023 y 2025 son años parciales: comparar porcentajes evita conclusiones falsas por volumen.", "P3", len(r3))
    out["p3_registros_dispositivo"] = r3

    # ------------------------------------------------------------------ campañas
    c = raw["campanas"].copy()
    c["inicio"], c["fin"] = _naive(c["inicio"]), _naive(c["fin"])
    for col in ("meta_likes", "meta_comentarios", "likes_reales", "comentarios_reales", "publicaciones"):
        c[col] = pd.to_numeric(c[col], errors="coerce").fillna(0).astype(int)
    reg.add("Estructural", "campanas", "metricas_objetivo.likes / .comentarios", "Aplanamiento de objeto anidado",
            "{metricas_objetivo: {likes: 692, ...}}", "meta_likes, meta_comentarios",
            "Deja la meta en la misma fila que el resultado para calcular cumplimiento.", "KPI campañas", len(c))
    reg.add("Estructural", "campanas", "publicaciones_asociadas", "Desanidado de arreglo ($unwind) y re-agrupación",
            "arreglo de ids", "conteo de likes y comentarios reales por campaña",
            "Las métricas reales viven en otras colecciones; hay que recorrer cada publicación asociada.", "KPI campañas", len(c))
    c["duracion_dias"] = (c["fin"] - c["inicio"]).dt.days
    c["cumplimiento_likes_pct"] = (c["likes_reales"] / c["meta_likes"].where(c["meta_likes"] > 0) * 100).round(2).fillna(0)
    c["cumplimiento_comentarios_pct"] = (c["comentarios_reales"] / c["meta_comentarios"].where(c["meta_comentarios"] > 0)
                                         * 100).round(2).fillna(0)
    c["estado"] = "Finalizada"
    c.loc[(c["inicio"] <= dia_ref) & (c["fin"] >= dia_ref), "estado"] = "Activa"
    c.loc[c["inicio"] > dia_ref, "estado"] = "Programada"
    reg.add("Semántica", "campanas", "cumplimiento_*_pct, estado", "Indicadores derivados",
            "likes 3 / meta 692", "0,43 % · 'Finalizada'",
            "Mide el impacto de cada campaña frente a su meta (división protegida si la meta es 0).", "KPI campañas", len(c))
    out["campanas"] = c[["campana_id", "nombre", "objetivo", "inicio", "fin", "duracion_dias", "estado", "publicaciones",
                         "meta_likes", "likes_reales", "cumplimiento_likes_pct", "meta_comentarios",
                         "comentarios_reales", "cumplimiento_comentarios_pct"]]

    reg.add("Limpieza", "fact_publicaciones", "contenido", "Filtro de registros de prueba ($match + $regex)",
            "'Publicación creada desde Postman'", "registro excluido en la consulta",
            "Las pruebas de la API no son actividad real y movían el 'día de hoy' del análisis a 2026.", "P1, P2",
            raw.get("_registros_prueba", 0))
    dup = int(raw.get("_duplicados_reacciones", 0))
    reg.add("Limpieza", "reacciones", "usuario_id + publicacion_id", "Control de duplicados",
            "misma reacción registrada dos veces", "se cuenta una vez (índice único en Atlas)",
            "Una reacción duplicada inflaría la interacción de una publicación.", "P1, P2", dup)

    contexto = {"dia_ref": dia_ref, "mes_ref": mes_ref, "anio_ref": anio_ref}
    return out, reg.df(), contexto
