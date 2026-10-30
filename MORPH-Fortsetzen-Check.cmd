@echo off
setlocal
set "TEMP=E:\MORPH-Studio\temp"
set "TMP=E:\MORPH-Studio\temp"
set "PYTHONDONTWRITEBYTECODE=1"
"E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe" -B "E:\MORPH-Studio\morph_pause.py" check
set "MORPH_CHECK_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %MORPH_CHECK_RESULT%
