@echo off
rem Starts the editor. Uses the Python launcher if installed, else pythonw on PATH.
where pyw >nul 2>nul && (start "" pyw "%~dp0save_editor.pyw" & exit /b)
start "" pythonw "%~dp0save_editor.pyw"