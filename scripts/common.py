"""Utilidades compartidas: rutas, logging y conexión a MongoDB Atlas."""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR_ANEXO = ROOT / "data" / "anexo"          # JSON originales del caso (Forma A)
DIR_PROCESADOS = ROOT / "data" / "processed"  # tablas limpias que lee Power BI
DIR_REPORTES = ROOT / "reportes"              # reporte automático de KPIs
DIR_LOGS = ROOT / "logs"
DIR_DOCS = ROOT / "docs"
for _d in (DIR_PROCESADOS, DIR_REPORTES, DIR_LOGS):
    _d.mkdir(parents=True, exist_ok=True)

COLECCIONES = ["usuarios", "publicaciones", "reacciones", "comentarios", "campañas"]


def get_logger(nombre: str = "pipeline") -> logging.Logger:
    """Logger con salida a consola y a logs/<nombre>.log (trazabilidad de cada ejecución)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # tildes correctas en la consola de Windows
    log = logging.getLogger(nombre)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    fh = RotatingFileHandler(DIR_LOGS / f"{nombre}.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(sh)
    return log


def get_db(log: logging.Logger):
    """Conecta a Atlas con la URI del archivo .env, verifica con ping y devuelve (client, db)."""
    from dotenv import load_dotenv
    from pymongo import MongoClient
    from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

    load_dotenv(ROOT / ".env")
    uri = os.getenv("MONGO_URI")
    nombre_db = os.getenv("MONGO_DB", "ContentFlow")
    if not uri:
        raise SystemExit("ERROR: falta MONGO_URI. Copia .env.example a .env y completa tus credenciales.")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000, appname="contentflow-ep3-pipeline")
        client.admin.command("ping")
    except (ServerSelectionTimeoutError, ConfigurationError, OperationFailure) as e:
        log.error("No se pudo conectar a Atlas (revisa MONGO_URI, IP Access List e internet). Detalle: %s", e)
        raise SystemExit("ERROR: no se pudo conectar a MongoDB Atlas.") from e
    db = client[nombre_db]
    faltantes = [c for c in COLECCIONES if c not in db.list_collection_names()]
    if faltantes:
        log.warning("Colecciones no encontradas en '%s': %s", nombre_db, faltantes)
    log.info("Conexión OK a Atlas, base '%s' (MongoDB %s)", nombre_db, client.server_info().get("version"))
    return client, db
