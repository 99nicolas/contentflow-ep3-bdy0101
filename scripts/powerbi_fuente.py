"""Conexión alternativa: Power BI ejecuta este script como origen de datos.

En Power BI Desktop: Inicio > Obtener datos > Más... > Otro > Script de Python, pega este archivo
y ajusta RUTA_REPO. Cada vez que se presiona "Actualizar", Power BI ejecuta el pipeline contra
MongoDB Atlas y recibe las tablas ya transformadas (sin pasar por el Excel intermedio).

Requisito: en Archivo > Opciones > Scripting de Python, el directorio de Python debe ser el
.venv del repositorio (tiene pymongo, pandas, python-dotenv y openpyxl).
"""
import sys

RUTA_REPO = r"C:\Users\nholc\Desktop\contentflow_proyecto\contentflow-ep3-bdy0101"
sys.path.insert(0, RUTA_REPO + r"\scripts")

from pipeline import ejecutar  # noqa: E402

_tablas, _registro, _ctx = ejecutar(offline=False, guardar=True)

# Power BI importa cada DataFrame que quede definido como variable global
fact_publicaciones = _tablas["fact_publicaciones"]
p1_sin_reaccion_dia = _tablas["p1_sin_reaccion_dia"]
p2_categoria_mes = _tablas["p2_categoria_mes"]
p3_registros_dispositivo = _tablas["p3_registros_dispositivo"]
dim_usuarios = _tablas["dim_usuarios"]
campanas = _tablas["campanas"]
kpis = _tablas["kpis"]
