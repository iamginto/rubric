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

# --- Tcl/Tk'nin kullanilmayan veri klasorleri ------------------------------
#
# Paketin 987 dosyasinin 922'si Tcl/Tk verisiydi ve cogu hic okunmuyor.
# Dosya sayisi acilisin bedeli: Defender ilk acilista klasoru dosya dosya
# tariyor. Atilanlar:
#   tzdata  - Tcl'in saat dilimi tablosu (609 dosya). rubric saati Python'un
#             time.strftime'indan aliyor, Tcl clock'a hic girmiyor.
#   msgs    - Tk iletisim kutulari icin ceviri katalogu. rubric Tk'nin kendi
#             kutularini kullanmiyor; dosya secici Windows'un kendi penceresi.
#   images  - Tk ornek gorselleri.
# Encoding tablolari **atilmiyor**: Tcl acilirken sistemin kod sayfasina ait
# olani ariyor, yanlis birini silmek baska makinede acilisi bozar.
ATILACAK = [("_internal", "_tcl_data", "tzdata"),
            ("_internal", "_tcl_data", "msgs"),
            ("_internal", "_tk_data", "msgs"),
            ("_internal", "_tk_data", "images")]

atilan = 0
for parcalar in ATILACAK:
    yol = os.path.join(DIST, "rubric", *parcalar)
    if os.path.isdir(yol):
        atilan += sum(len(d) for _, _, d in os.walk(yol))
        shutil.rmtree(yol, ignore_errors=True)

kalan = sum(len(d) for _, _, d in os.walk(os.path.join(DIST, "rubric")))
print(f"\nkullanilmayan Tcl/Tk verisi atildi: {atilan} dosya, kalan {kalan}")
print("hazir:", os.path.join(DIST, "rubric", "rubric.exe"))
