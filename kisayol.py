# -*- coding: utf-8 -*-
"""
Masaustune rubric kisayolu ve ikonunu kurar.

    uv run kisayol.py

Neden .exe degil: pythonw.exe'yi dogrudan hedefleyen bir .lnk cift tiklamada
konsolsuz acilir, uzerine surukledigin dosyayi argüman olarak gecirir ve
kodu degistirince yeniden derleme gerektirmez. PyInstaller ile gercek bir
exe de uretilebilir ama ~30 MB tasir ve her degisiklikte yeniden paketlenir.
"""

from __future__ import annotations

import os
import struct
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rubric  # noqa: E402  (ikon uygulamanin paletini kullansin)

KOK = os.path.dirname(os.path.abspath(__file__))
IKON = os.path.join(KOK, "rubric.ico")
PYW = os.path.join(KOK, ".venv", "Scripts", "pythonw.exe")

# Renkler uygulamanin ayar tablosundan; tema degisince ikon da doner.
ZEMIN = rubric.renk("zemin")
VURGU = rubric.renk("vurgu")
CERCEVE = rubric.renk("palet-cerceve")


def ikon_uret(yol: str = IKON) -> str:
    """256x256 bir ikon cizer ve PNG'yi ICO kabugunun icine koyar.

    Vista'dan beri ICO, icinde dogrudan PNG tasiyabiliyor; bu yuzden BMP'ye
    cevirmeye ve maske duzlemi uretmeye gerek yok.
    """
    belge = pymupdf.open()
    sayfa = belge.new_page(width=256, height=256)
    sayfa.draw_rect(sayfa.rect, color=None, fill=ZEMIN)
    sayfa.draw_rect(pymupdf.Rect(10, 10, 246, 246), color=CERCEVE, width=6)
    sayfa.insert_font(fontname="consb", fontfile=r"C:\Windows\Fonts\consolab.ttf")
    # Terminal istemi gibi:  >_
    sayfa.insert_text((44, 168), ">", fontsize=150, fontname="consb", color=VURGU)
    sayfa.draw_rect(pymupdf.Rect(128, 150, 212, 168), color=None, fill=VURGU)

    png = sayfa.get_pixmap(alpha=False).tobytes("png")
    belge.close()

    with open(yol, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, 1))              # ICONDIR
        f.write(struct.pack("<BBBBHHII",
                            0, 0,      # 0 = 256 piksel
                            0, 0, 1, 32,
                            len(png), 22))                 # ICONDIRENTRY
        f.write(png)
    return yol


def _ps(metin: str) -> str:
    """PowerShell'in tek tirnakli dizesi. Icindeki ' ikilenir; yoksa yolunda
    kesme isareti olan bir klasor (D'Angelo) betigi bozar, hatta klasor
    adiyla araya komut sokulabilir."""
    return "'" + metin.replace("'", "''") + "'"


def kisayol_kur(hedef: str | None = None) -> str:
    """.lnk'yi kurar. pywin32 yok, kisayolu PowerShell'in COM'u olusturuyor."""
    hedef = hedef or os.path.join(rubric.masaustu_yolu(), "rubric.lnk")
    arguman = f'"{os.path.join(KOK, "rubric.py")}"'     # yolda bosluk olabilir
    betik = (
        "$w = New-Object -ComObject WScript.Shell; "
        f"$k = $w.CreateShortcut({_ps(hedef)}); "
        f"$k.TargetPath = {_ps(PYW)}; "
        f"$k.Arguments = {_ps(arguman)}; "
        f"$k.WorkingDirectory = {_ps(KOK)}; "
        f"$k.IconLocation = {_ps(IKON)}; "
        "$k.Description = 'rubric - vim tuslu belge okuyucu'; "
        "$k.Save()"
    )
    import subprocess
    sonuc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", betik],
        capture_output=True, text=True)
    if sonuc.returncode != 0:
        raise RuntimeError(sonuc.stderr.strip() or "kisayol kurulamadi")
    return hedef


if __name__ == "__main__":
    if not os.path.exists(PYW):
        sys.exit(f"pythonw yok: {PYW}  ('uv sync' calistir)")
    print("ikon    :", ikon_uret())
    print("kisayol :", kisayol_kur())
