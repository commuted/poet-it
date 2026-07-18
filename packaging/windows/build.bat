@echo off
:: Poet-it Windows standalone build
:: Run this from the project root:  packaging\windows\build.bat
::
:: Prerequisites (run once):
::   pip install pyinstaller

cd /d "%~dp0..\.."

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

echo Building Poet-it...
pyinstaller packaging\windows\poet-it.spec --clean --noconfirm

echo.
echo Done. Run:  dist\Poet-it\Poet-it.exe
