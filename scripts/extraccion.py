"""EXTRACCIÓN (IE1): consultas de agregación sobre MongoDB Atlas.

Cada consulta trae solo los atributos que la tabla RICE decidió conservar, resuelve en el servidor
los cruces entre colecciones ($lookup), desarma arreglos ($unwind) y lee campos anidados
(metricas_objetivo.likes). Así viaja poco dato y Python recibe filas listas para transformar.

Las mismas tablas se pueden construir en modo --offline desde los JSON del anexo (data/anexo),
para probar el pipeline sin conexión. El modo normal siempre lee desde Atlas.
"""
import json
import time
from datetime import datetime, timedelta

import pandas as pd

from common import COLECCIONES, DIR_ANEXO

# ------------------------------------------------------------------ consultas MongoDB (pipelines)

# Limpieza en origen: las publicaciones creadas al probar la API con Postman no son datos del negocio
FILTRO_PRUEBAS = {"contenido": {"$not": {"$regex": "desde postman", "$options": "i"}}}
MATCH_PRUEBAS = {"$match": FILTRO_PRUEBAS}

# E1 · Publicaciones con sus conteos de reacciones y comentarios (preguntas P1 y P2)
PIPE_PUBLICACIONES = [
    MATCH_PRUEBAS,                                                       # filtro: excluye registros de prueba
    {"$project": {"usuario_id": 1, "categoria": 1, "tipo": 1,
                  "fecha": {"$toDate": "$fecha_publicacion"}}},          # formato: texto/fecha -> Date
    {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id",
                 "pipeline": [{"$count": "n"}], "as": "r"}},             # cruce publicaciones-reacciones
    {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id",
                 "pipeline": [{"$group": {"_id": None, "n": {"$sum": 1}, "likes": {"$sum": "$likes"}}}],
                 "as": "c"}},                                            # cruce publicaciones-comentarios
    {"$project": {"_id": 0, "publicacion_id": "$_id", "usuario_id": 1, "categoria": 1, "tipo": 1, "fecha": 1,
                  "reacciones": {"$ifNull": [{"$first": "$r.n"}, 0]},
                  "comentarios": {"$ifNull": [{"$first": "$c.n"}, 0]},
                  "likes_comentarios": {"$ifNull": [{"$first": "$c.likes"}, 0]}}},
    {"$sort": {"fecha": 1}},
]


def pipe_sin_reaccion(dia: datetime) -> list:
    """E2 · P1 operacional: publicaciones de un día que todavía no tienen ninguna reacción."""
    return [
        {"$match": {"fecha_publicacion": {"$gte": dia, "$lt": dia + timedelta(days=1)}, **FILTRO_PRUEBAS}},  # filtro por día
        {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id",
                     "pipeline": [{"$limit": 1}], "as": "r"}},
        {"$match": {"r": {"$size": 0}}},                                 # condición: sin reacciones
        {"$project": {"_id": 0, "publicacion_id": "$_id", "categoria": 1, "tipo": 1,
                      "fecha": {"$toDate": "$fecha_publicacion"}}},
        {"$sort": {"fecha": 1}},
    ]


# E3 · P3 estratégico: registros por año y dispositivo
PIPE_REGISTROS = [
    {"$project": {"dispositivo": 1, "anio": {"$year": {"$toDate": "$fecha_registro"}}}},
    {"$group": {"_id": {"anio": "$anio", "dispositivo": "$dispositivo"}, "registros": {"$sum": 1}}},
    {"$project": {"_id": 0, "anio": "$_id.anio", "dispositivo": "$_id.dispositivo", "registros": 1}},
    {"$sort": {"anio": 1, "dispositivo": 1}},
]

# E4 · Usuarios sin datos personales (nombre, correo y país se descartan por RICE y privacidad)
PIPE_USUARIOS = [
    {"$project": {"_id": 0, "usuario_id": "$_id", "genero": 1, "dispositivo": 1,
                  "fecha_registro": {"$toDate": "$fecha_registro"}}},
]


def _marca(pub: int, rea: int, com: int) -> dict:
    return {"$project": {"usuario_id": 1, "p": {"$literal": pub}, "r": {"$literal": rea}, "c": {"$literal": com}}}


# E5 · Actividad por usuario (usuarios más activos): une tres colecciones con $unionWith
PIPE_ACTIVIDAD = [
    MATCH_PRUEBAS,
    _marca(1, 0, 0),
    {"$unionWith": {"coll": "reacciones", "pipeline": [_marca(0, 1, 0)]}},
    {"$unionWith": {"coll": "comentarios", "pipeline": [_marca(0, 0, 1)]}},
    {"$group": {"_id": "$usuario_id", "publicaciones": {"$sum": "$p"},
                "reacciones": {"$sum": "$r"}, "comentarios": {"$sum": "$c"}}},
    {"$project": {"_id": 0, "usuario_id": "$_id", "publicaciones": 1, "reacciones": 1, "comentarios": 1}},
]

# E6 · Campañas: lee el objeto anidado metricas_objetivo y desarma el arreglo publicaciones_asociadas
PIPE_CAMPANAS = [
    {"$project": {"nombre": 1, "objetivo": 1,
                  "inicio": {"$toDate": "$fecha_inicio"}, "fin": {"$toDate": "$fecha_fin"},
                  "meta_likes": "$metricas_objetivo.likes",
                  "meta_comentarios": "$metricas_objetivo.comentarios",
                  "pub": "$publicaciones_asociadas"}},
    {"$unwind": {"path": "$pub", "preserveNullAndEmptyArrays": True}},
    {"$lookup": {"from": "reacciones", "localField": "pub", "foreignField": "publicacion_id",
                 "pipeline": [{"$match": {"tipo_reaccion": "Me gusta"}}, {"$count": "n"}], "as": "lk"}},
    {"$lookup": {"from": "comentarios", "localField": "pub", "foreignField": "publicacion_id",
                 "pipeline": [{"$count": "n"}], "as": "cm"}},
    {"$group": {"_id": "$_id", "nombre": {"$first": "$nombre"}, "objetivo": {"$first": "$objetivo"},
                "inicio": {"$first": "$inicio"}, "fin": {"$first": "$fin"},
                "meta_likes": {"$first": "$meta_likes"}, "meta_comentarios": {"$first": "$meta_comentarios"},
                "publicaciones": {"$sum": {"$cond": [{"$ifNull": ["$pub", False]}, 1, 0]}},
                "likes_reales": {"$sum": {"$ifNull": [{"$first": "$lk.n"}, 0]}},
                "comentarios_reales": {"$sum": {"$ifNull": [{"$first": "$cm.n"}, 0]}}}},
    {"$project": {"_id": 0, "campana_id": "$_id", "nombre": 1, "objetivo": 1, "inicio": 1, "fin": 1,
                  "meta_likes": 1, "meta_comentarios": 1, "publicaciones": 1,
                  "likes_reales": 1, "comentarios_reales": 1}},
    {"$sort": {"campana_id": 1}},
]

# Control de calidad: reacciones duplicadas (mismo usuario y publicación)
PIPE_DUPLICADOS = [
    {"$group": {"_id": {"u": "$usuario_id", "p": "$publicacion_id"}, "n": {"$sum": 1}}},
    {"$match": {"n": {"$gt": 1}}},
    {"$count": "grupos"},
]

CONSULTAS = {  # nombre -> (colección, pipeline, pregunta o uso)
    "publicaciones": ("publicaciones", PIPE_PUBLICACIONES, "P1 y P2"),
    "registros_dispositivo": ("usuarios", PIPE_REGISTROS, "P3"),
    "usuarios": ("usuarios", PIPE_USUARIOS, "Dimensión de usuarios"),
    "actividad": ("publicaciones", PIPE_ACTIVIDAD, "Usuarios más activos"),
    "campanas": ("campañas", PIPE_CAMPANAS, "Impacto de campañas"),
}


def extraer_atlas(db, log) -> dict:
    """Ejecuta todas las consultas en Atlas y devuelve un DataFrame por consulta."""
    datos, tiempos = {}, []
    for nombre, (coleccion, pipeline, uso) in CONSULTAS.items():
        t0 = time.perf_counter()
        filas = list(db[coleccion].aggregate(pipeline, allowDiskUse=False))
        ms = (time.perf_counter() - t0) * 1000
        datos[nombre] = pd.DataFrame(filas)
        tiempos.append({"consulta": nombre, "coleccion": coleccion, "uso": uso, "filas": len(filas), "ms": round(ms, 1)})
        log.info("Extracción %-22s %-14s filas=%4d  %.0f ms", nombre, coleccion, len(filas), ms)
    datos["_registros_prueba"] = db.publicaciones.count_documents({"contenido": {"$regex": "desde postman", "$options": "i"}})
    log.info("Registros de prueba excluidos por el filtro: %d", datos["_registros_prueba"])
    dup = list(db.reacciones.aggregate(PIPE_DUPLICADOS))
    datos["_duplicados_reacciones"] = dup[0]["grupos"] if dup else 0
    datos["_metricas_extraccion"] = pd.DataFrame(tiempos)
    return datos


def sin_reaccion_atlas(db, dia: datetime) -> pd.DataFrame:
    return pd.DataFrame(list(db.publicaciones.aggregate(pipe_sin_reaccion(dia))))


# ------------------------------------------------------------------ modo offline (mismo resultado desde JSON)

def _leer(nombre: str) -> pd.DataFrame:
    with open(DIR_ANEXO / f"{nombre}.json", encoding="utf-8") as f:
        return pd.DataFrame(json.load(f))


def extraer_offline(log) -> dict:
    """Replica con pandas las consultas de Atlas a partir de los JSON del anexo (solo para pruebas)."""
    u, p, r, c, k = (_leer(n) for n in COLECCIONES)
    prueba = p["contenido"].astype(str).str.contains("desde postman", case=False)
    p = p[~prueba]
    dup = int(r.duplicated(["usuario_id", "publicacion_id"]).sum())
    r = r.drop_duplicates(["usuario_id", "publicacion_id"], keep="first")  # en Atlas lo impide el índice único
    nr = r.groupby("publicacion_id").size()
    gc = c.groupby("publicacion_id").agg(n=("_id", "size"), likes=("likes", "sum"))
    pub = p.rename(columns={"_id": "publicacion_id"})[["publicacion_id", "usuario_id", "categoria", "tipo", "fecha_publicacion"]]
    pub["fecha"] = pd.to_datetime(pub.pop("fecha_publicacion"))
    pub["reacciones"] = pub.publicacion_id.map(nr).fillna(0).astype(int)
    pub["comentarios"] = pub.publicacion_id.map(gc["n"]).fillna(0).astype(int)
    pub["likes_comentarios"] = pub.publicacion_id.map(gc["likes"]).fillna(0).astype(int)

    us = u.rename(columns={"_id": "usuario_id"})[["usuario_id", "genero", "dispositivo", "fecha_registro"]].copy()
    us["fecha_registro"] = pd.to_datetime(us["fecha_registro"])
    reg = (us.assign(anio=us.fecha_registro.dt.year).groupby(["anio", "dispositivo"]).size()
             .rename("registros").reset_index())

    act = pd.concat([p[["usuario_id"]].assign(publicaciones=1, reacciones=0, comentarios=0),
                     r[["usuario_id"]].assign(publicaciones=0, reacciones=1, comentarios=0),
                     c[["usuario_id"]].assign(publicaciones=0, reacciones=0, comentarios=1)])
    act = act.groupby("usuario_id").sum().reset_index()

    likes = r[r.tipo_reaccion == "Me gusta"].groupby("publicacion_id").size()
    ex = k.explode("publicaciones_asociadas")
    ex["lk"] = ex.publicaciones_asociadas.map(likes).fillna(0)
    ex["cm"] = ex.publicaciones_asociadas.map(gc["n"]).fillna(0)
    camp = ex.groupby("_id").agg(nombre=("nombre", "first"), objetivo=("objetivo", "first"),
                                 inicio=("fecha_inicio", "first"), fin=("fecha_fin", "first"),
                                 metricas=("metricas_objetivo", "first"),
                                 publicaciones=("publicaciones_asociadas", "count"),
                                 likes_reales=("lk", "sum"), comentarios_reales=("cm", "sum")).reset_index()
    camp["meta_likes"] = camp.metricas.str["likes"]
    camp["meta_comentarios"] = camp.metricas.str["comentarios"]
    camp = camp.drop(columns="metricas").rename(columns={"_id": "campana_id"})
    camp[["inicio", "fin"]] = camp[["inicio", "fin"]].apply(pd.to_datetime)

    log.info("Extracción offline desde %s (JSON del anexo)", DIR_ANEXO)
    return {"publicaciones": pub, "registros_dispositivo": reg, "usuarios": us, "actividad": act,
            "campanas": camp, "_duplicados_reacciones": dup, "_registros_prueba": int(prueba.sum()),
            "_metricas_extraccion": pd.DataFrame([{"consulta": n, "coleccion": "JSON", "uso": "offline",
                                                    "filas": len(d), "ms": None} for n, d in
                                                   [("publicaciones", pub), ("registros_dispositivo", reg),
                                                    ("usuarios", us), ("actividad", act), ("campanas", camp)]])}


def sin_reaccion_offline(publicaciones: pd.DataFrame, dia: datetime) -> pd.DataFrame:
    p = publicaciones
    m = (p.fecha >= dia) & (p.fecha < dia + timedelta(days=1)) & (p.reacciones == 0)
    return p.loc[m, ["publicacion_id", "categoria", "tipo", "fecha"]].reset_index(drop=True)
