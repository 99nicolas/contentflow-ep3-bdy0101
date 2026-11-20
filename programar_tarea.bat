@echo off
REM Registra una tarea en el Programador de tareas de Windows que ejecuta el pipeline cada hora.
REM Para quitarla: schtasks /Delete /TN "ContentFlow_EP3_Pipeline" /F
schtasks /Create /SC HOURLY /MO 1 /TN "ContentFlow_EP3_Pipeline" /TR "\"%~dp0ejecutar_pipeline.bat\"" /F
schtasks /Query /TN "ContentFlow_EP3_Pipeline" /V /FO LIST
pause
