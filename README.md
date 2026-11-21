# ContentFlow · EP3 BDY0101 — Explotación de datos NoSQL para el análisis organizacional

**Equipo:** Edgard Hernandez · Carlos Caceres · Nicolas Holck
**Caso:** Forma A — ContentFlow (usuarios, publicaciones, reacciones, comentarios y campañas en MongoDB Atlas)

Pipeline ETL en Python que extrae datos de MongoDB Atlas con agregaciones, los transforma con pandas, calcula KPIs con meta y semáforo, alimenta un dashboard de Power BI y genera un reporte automático de KPIs.

📄 Informe técnico: [`docs/ContentFlow_EP3_Informe_Tecnico.pdf`](docs/ContentFlow_EP3_Informe_Tecnico.pdf)
📊 Dashboard: [`powerbi/ContentFlow_EP3_Dashboard.pbix`](powerbi/ContentFlow_EP3_Dashboard.pbix)
🗺️ Arquitectura: [`docs/diagrama_arquitectura.png`](docs/diagrama_arquitectura.png) · Boceto final: [`docs/boceto_dashboard_final.png`](docs/boceto_dashboard_final.png)

## Preguntas de negocio (una por nivel de decisión)

| Nivel | Pregunta | Atributos conservados (RICE) |
|---|---|---|
| Operacional | ¿Qué publicaciones del día todavía no reciben ninguna reacción? | fecha_publicacion, reacciones.publicacion_id |
| Táctica | ¿Qué categoría de contenido genera más interacciones por publicación cada mes? | categoria, fecha_publicacion → mes, publicacion_id |
| Estratégica | ¿Qué tipo de dispositivo crece más entre los usuarios nuevos, año a año? | dispositivo, fecha_registro → año |

Las tablas RICE completas (con el porqué de cada puntaje), las transformaciones de cada pregunta (antes → después) y sus conclusiones están en la sección 2 del informe, en `config/rice.csv` y `config/transformaciones_por_pregunta.csv`, y en las páginas **P1 · Operacional**, **P2 · Táctica** y **P3 · Estratégica** del dashboard. El pipeline agrega ambas tablas al Excel que lee Power BI (hojas `rice` y `transformaciones_pregunta`).

🎤 Presentación: [`docs/ContentFlow_EP3_Presentacion.pptx`](docs/ContentFlow_EP3_Presentacion.pptx)

## KPIs (valores de la última ejecución contra Atlas)

| KPI | Nivel | Valor | Meta | Estado |
|---|---|---|---|---|
| K1 Publicaciones del día sin reacción | Operacional | 75,0 % | ≤ 30 % | 🔴 |
| K2 Interacciones por publicación (último mes cerrado) | Táctico | 2,04 | ≥ 2,0 | 🟢 |
| K3 Participación de Móvil en nuevos registros | Estratégico | 38,0 % | ≥ 40 % | 🟡 |
| K4 Cumplimiento promedio de la meta de likes | Táctico | 0,18 % | ≥ 100 % | 🔴 |
| K5 Usuarios activos | Táctico | 93,8 % | ≥ 80 % | 🟢 |

## Estructura

```
scripts/
  common.py           conexión a Atlas (.env), rutas y logging
  extraccion.py       5 agregaciones ($match, $lookup, $unwind, $unionWith, $group) + modo offline
  transformacion.py   18 transformaciones documentadas (estructural, semántica, formato, limpieza)
  kpis.py             KPIs con meta, semáforo e historial
  reporte.py          reporte HTML automático
  pipeline.py         orquesta todo el flujo
  powerbi_fuente.py   alternativa: el pipeline como origen "Script de Python" en Power BI
config/metas_kpi.json metas y tolerancias de cada KPI
data/anexo/           JSON originales del caso
data/processed/       tablas para Power BI (contentflow_ep3.xlsx y CSV) + kpis_historial.csv
reportes/             reporte_kpis.html (se regenera en cada ejecución)
powerbi/              dashboard .pbix
docs/                 informe, diagrama, boceto, transformaciones.csv, consultas_extraccion.csv
evidencias/           capturas del dashboard, del modelo y del reporte
logs/pipeline.log     trazabilidad de las ejecuciones
ejecutar_pipeline.bat · programar_tarea.bat
```

## Cómo ejecutar (Windows)

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          :: completar MONGO_URI con el usuario de Atlas
.venv\Scripts\python scripts\pipeline.py              :: contra MongoDB Atlas
.venv\Scripts\python scripts\pipeline.py --offline    :: desde data/anexo, sin conexión
programar_tarea.bat                                    :: ejecución automática cada hora
```

Luego, en Power BI Desktop, abrir `powerbi/ContentFlow_EP3_Dashboard.pbix` y presionar **Actualizar**.

> El archivo `.env` con las credenciales nunca se sube al repositorio (está en `.gitignore`).

## Proyecto anterior

La carga de datos, las consultas, el CRUD y la API REST de la EP2 están en [99nicolas/contentflow-bdy0101](https://github.com/99nicolas/contentflow-bdy0101).
