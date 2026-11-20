@echo off
REM Ejecuta el pipeline ETL completo (Atlas -> transformacion -> Power BI -> KPIs -> reporte).
REM Lo usa el Programador de tareas de Windows (ver programar_tarea.bat).
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
"%PY%" scripts\pipeline.py %*
