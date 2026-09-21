# -*- coding: utf-8 -*-
"""
rubric'i Windows'un "Birlikte ac" listesine ve PDF uygulamalari arasina kaydeder.

    uv run birlikte-ac.py            # kaydet
    uv run birlikte-ac.py --kaldir   # kaydi sil
    uv run birlikte-ac.py --durum    # ne kayitli, varsayilan kim

Yalnizca **HKEY_CURRENT_USER** altina yazar: yonetici gerekmez, baska
kullaniciya dokunmaz, `--kaldir` hepsini geri alir.

Windows'un varsayilan PDF uygulamasini buradan **degistiremeyiz**: Windows 10'dan
beri `UserChoice` anahtari kullanicinin secimiyle uretilen bir imza tasiyor ve
disaridan yazilani gecersiz sayiyor. Bu betik rubric'i listede gorunur yapar,
"her zaman bununla ac"i kullanicinin kendisi bir kez secer.

Hedef olarak once `dist\\rubric\\rubric.exe` alinir (exe varsa en hizlisi odur),
yoksa `rubric.cmd`. Exe'yi yeniden uretince yol degismedigi icin tekrar
calistirmak gerekmez; klasoru tasirsan gerekir.
"""

from __future__ import annotations

import ctypes
import os
import sys
import winreg

KOK = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(KOK, "dist", "rubric", "rubric.exe")
CMD = os.path.join(KOK, "rubric.cmd")
IKON = os.path.join(KOK, "rubric.ico")

PROGID = "rubric.pdf"              # rubric'in kendi dosya turu kimligi
UYGULAMA = "rubric.exe"            # Applications\<ad>: "Birlikte ac" listesi bunu okur
YETENEK = r"Software\rubric\Capabilities"


def hedef() -> str:
    return EXE if os.path.exists(EXE) else CMD


def komut(yol: str) -> str:
    return f'"{yol}" "%1"'


def yaz(kok, yol: str, deger: str = "", ad: str = "") -> None:
    with winreg.CreateKey(kok, yol) as k:
        winreg.SetValueEx(k, ad, 0, winreg.REG_SZ, deger)


def agaci_sil(kok, yol: str) -> bool:
    """Anahtari alt anahtarlariyla siler; yoksa False."""
    try:
        with winreg.OpenKey(kok, yol, 0, winreg.KEY_READ) as k:
            alt = [winreg.EnumKey(k, i) for i in range(winreg.QueryInfoKey(k)[0])]
    except FileNotFoundError:
        return False
    for a in alt:
        agaci_sil(kok, yol + "\\" + a)
    winreg.DeleteKey(kok, yol)
    return True


def kabugu_uyar() -> None:
    """SHCNE_ASSOCCHANGED: Explorer dosya turu kayitlarini yeniden okusun."""
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass


def kaydet() -> None:
    yol = hedef()
    if not os.path.exists(yol):
        sys.exit(f"hedef bulunamadi: {yol}\n(once `uv run --with pyinstaller exe-yap.py`)")
    k = winreg.HKEY_CURRENT_USER
    c = komut(yol)
    ikon = f"{IKON},0" if os.path.exists(IKON) else f"{yol},0"

    # 1) rubric'in dosya turu: adi, ikonu, acma komutu
    yaz(k, rf"Software\Classes\{PROGID}", "PDF belgesi (rubric)")
    yaz(k, rf"Software\Classes\{PROGID}", "PDF belgesi (rubric)", "FriendlyTypeName")
    yaz(k, rf"Software\Classes\{PROGID}\DefaultIcon", ikon)
    yaz(k, rf"Software\Classes\{PROGID}\shell\open", "rubric ile &aç")
    yaz(k, rf"Software\Classes\{PROGID}\shell\open\command", c)

    # 2) "Birlikte ac" listesi Applications\<exe adi> altini okur
    yaz(k, rf"Software\Classes\Applications\{UYGULAMA}", "rubric", "FriendlyAppName")
    yaz(k, rf"Software\Classes\Applications\{UYGULAMA}\DefaultIcon", ikon)
    yaz(k, rf"Software\Classes\Applications\{UYGULAMA}\shell\open\command", c)
    yaz(k, rf"Software\Classes\Applications\{UYGULAMA}\SupportedTypes", "", ".pdf")

    # 3) .pdf'in "birlikte ac" onerileri arasina rubric'i koy
    yaz(k, r"Software\Classes\.pdf\OpenWithProgids", "", PROGID)

    # 4) Ayarlar > Varsayilan uygulamalar listesinde gorunsun
    yaz(k, YETENEK, "rubric", "ApplicationName")
    yaz(k, YETENEK, "zathura tadinda, vim tuslu PDF okuyucu", "ApplicationDescription")
    yaz(k, YETENEK + r"\FileAssociations", PROGID, ".pdf")
    yaz(k, r"Software\RegisteredApplications", YETENEK, "rubric")

    kabugu_uyar()
    print(f"kaydedildi: {yol}\n")
    print("Varsayilan yapmak icin (Windows disaridan degistirtmiyor):")
    print("  bir PDF'e sag tik > Birlikte ac > Baska uygulama sec > rubric >")
    print("  'Her zaman bu uygulamayi kullan' > Tamam")
    print("  ya da: Ayarlar > Uygulamalar > Varsayilan uygulamalar > rubric")


def kaldir() -> None:
    k = winreg.HKEY_CURRENT_USER
    silinen = 0
    for yol in (rf"Software\Classes\{PROGID}",
                rf"Software\Classes\Applications\{UYGULAMA}",
                r"Software\rubric"):
        silinen += agaci_sil(k, yol)
    for yol, ad in ((r"Software\Classes\.pdf\OpenWithProgids", PROGID),
                    (r"Software\RegisteredApplications", "rubric")):
        try:
            with winreg.OpenKey(k, yol, 0, winreg.KEY_SET_VALUE) as anahtar:
                winreg.DeleteValue(anahtar, ad)
                silinen += 1
        except FileNotFoundError:
            pass
    kabugu_uyar()
    print(f"kaldirildi ({silinen} kayit)")
    print("Varsayilan uygulama secimi kullanicinin kendi secimi; onu Windows tutar:")
    print("  Ayarlar > Uygulamalar > Varsayilan uygulamalar > .pdf")


def oku(kok, yol: str, ad: str = "") -> str | None:
    try:
        with winreg.OpenKey(kok, yol) as k:
            return winreg.QueryValueEx(k, ad)[0]
    except OSError:
        return None


def durum() -> None:
    k = winreg.HKEY_CURRENT_USER
    print("hedef       :", hedef(), "" if os.path.exists(hedef()) else "(YOK)")
    print("progid      :", oku(k, rf"Software\Classes\{PROGID}\shell\open\command") or "-")
    print("uygulama    :",
          oku(k, rf"Software\Classes\Applications\{UYGULAMA}\shell\open\command") or "-")
    print("openwith    :",
          "var" if oku(k, r"Software\Classes\.pdf\OpenWithProgids", PROGID) is not None else "-")
    print("kayitli app :", oku(k, r"Software\RegisteredApplications", "rubric") or "-")
    secim = oku(k, r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                   r"\FileExts\.pdf\UserChoice", "ProgId")
    print(".pdf su an  :", secim or "-")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg in ("--kaldir", "-k"):
        kaldir()
    elif arg in ("--durum", "-d"):
        durum()
    elif arg:
        sys.exit(__doc__)
    else:
        kaydet()
