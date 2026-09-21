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
# Kivrik kose ve sayfa satirlari: vurgunun zemine dogru koyulmus hali
KOYU = tuple(0.6 * v + 0.4 * z for v, z in zip(VURGU, ZEMIN))


def ikon_uret(yol: str = IKON) -> str:
    """256x256 bir ikon cizer ve PNG'yi ICO kabugunun icine koyar.

    Vista'dan beri ICO, icinde dogrudan PNG tasiyabiliyor; bu yuzden BMP'ye
    cevirmeye ve maske duzlemi uretmeye gerek yok.
    """
    belge = pymupdf.open()
    sayfa = belge.new_page(width=256, height=256)
    sayfa.draw_rect(sayfa.rect, color=None, fill=ZEMIN)

    def cokgen(renk, *noktalar):
        sayfa.draw_polyline([pymupdf.Point(x, y) for x, y in noktalar],
                            color=None, fill=renk, closePath=True)

    # "sayfa-r": r'nin kolu kosesi kivrik kucuk bir sayfa. Sap ile kol tek
    # cokgen: ayri cizilince ortak kenarda kenar yumusatmasi cizgi birakir.
    cokgen(VURGU, (72, 60), (160, 60), (184, 84), (184, 104),
           (108, 104), (108, 208), (72, 208))
    cokgen(KOYU, (160, 60), (160, 84), (184, 84))
    sayfa.draw_rect(pymupdf.Rect(120, 76, 148, 80), color=None, fill=KOYU)
    sayfa.draw_rect(pymupdf.Rect(120, 88, 172, 92), color=None, fill=KOYU)

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
