@echo off
rem rubric - her yerden calistirmak icin. PDF dosyasini bunun uzerine surukleyip
rem birakabilir, ya da .pdf uzantisini buna baglayabilirsin.
rem
rem pythonw dogrudan cagriliyor: "uv run pythonw" bu isi beceremiyor, ayrica
rem boylece acilista uv'nin cozumleme gecikmesi de yok. Konsol penceresi acilmaz.

if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo .venv yok, kuruluyor...
    pushd "%~dp0"
    uv sync
    popd
)

rem /b: yeni bir konsol penceresi acmadan baslat.
start "" /b "%~dp0.venv\Scripts\pythonw.exe" "%~dp0rubric.py" %*
