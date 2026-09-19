# -*- coding: utf-8 -*-
"""
rubric'i konsolsuz bir exe'ye paketler:  dist\\rubric\\rubric.exe

    uv run --with pyinstaller exe-yap.py

Neden tek dosya (--onefile) degil: tek dosyalik exe her acilista icindeki
~60 MB'i %TEMP%'e acar, Defender da o yeni klasoru her seferinde yeniden
tarar. Acilis 1.5-3 sn suruyordu (ayni kod pythonw ile 0.3 sn); exe cokunce
ya da zorla kapaninca acilan klasor %TEMP%'te kaliyordu. Klasorlu (--onedir)
exe dosyalarini yerinde kullanir: acilis ~0.3 sn, Defender yalnizca ilk
acilista tarar. Baskasina vermek icin dist\\rubric klasorunu zip'le.

PyInstaller projenin bagimliligi degil, `--with` ile yalnizca bu calismada
gelir. Exe kodun o anki halinin fotografidir: rubric.py degisince bunu yeniden
calistir. rubricrc exe'ye gomulmez, yine %APPDATA%\\rubric\\rubricrc'den okunur.
"""

import os
import shutil

import PyInstaller.__main__

KOK = os.path.dirname(os.path.abspath(__file__))
IKON = os.path.join(KOK, "rubric.ico")
INSA = os.path.join(KOK, "build")
DIST = os.path.join(KOK, "dist")

PyInstaller.__main__.run([
    os.path.join(KOK, "rubric.py"),
    "--name", "rubric",
    "--onedir",                             # klasor: her acilista acilmaz
    "--windowed",                           # konsol penceresi acilmasin
    "--icon", IKON,                         # exe dosyasinin ikonu
    "--add-data", f"{IKON}{os.pathsep}.",   # pencere / gorev cubugu ikonu
    # rubric internete baglanmaz: SSL ve OpenSSL (libcrypto + libssl, ~9 MB)
    # gereksiz. hashlib OpenSSL'siz kendi yerlesik algoritmalarina duser.
    "--exclude-module", "ssl",
    "--exclude-module", "_ssl",
    "--exclude-module", "_hashlib",
    "--distpath", DIST,
    "--workpath", INSA,
    "--specpath", INSA,
    "--noconfirm",
    "--clean",
])

shutil.rmtree(INSA, ignore_errors=True)     # ara dosyalar, exe'ye gerek yok

# Eski tek dosyalik surum kaldiysa kaldir: yanlislikla yavas olan acilmasin.
eski = os.path.join(DIST, "rubric.exe")
if os.path.isfile(eski):
    try:
        os.remove(eski)
    except OSError as e:
        print(f"eski {eski} silinemedi (acik mi?): {e}")

print("\nhazir:", os.path.join(DIST, "rubric", "rubric.exe"))
