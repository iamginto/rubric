# -*- coding: utf-8 -*-
"""fare.py'nin surdugu rubric penceresi. Kendi basina calistirilmaz.

Gecici veri/ayar dizini kullanir, en ustte durur ve pencere bilgisini
(hwnd, mantiksal boyut, bar yuksekligi) bir dosyaya yazar. Sure dolunca
cik() cagirmadan kapanir: durum.json'a hic yazilmaz.
"""
import json
import sys
import tempfile

import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric

gecici = tempfile.mkdtemp(prefix="rubric-fare-")
rubric.veri_dizini = lambda: gecici
rubric.ayar_dizini = lambda: gecici

pdf, bilgi_dosyasi, sure = sys.argv[1], sys.argv[2], int(sys.argv[3])
u = rubric.Rubric(pdf if pdf != "-" else None)
u.geometry("800x500+300+200")
u.attributes("-topmost", True)
u.after(80, u.yenile)


def bilgi_yaz():
    u.update_idletasks()
    with open(bilgi_dosyasi, "w", encoding="utf-8") as f:
        json.dump({
            "hwnd": int(u.wm_frame(), 16),
            "gen": u.winfo_width(), "yuk": u.winfo_height(),
            "bar_y": u.ust_bar.winfo_y(), "bar_h": u.ust_bar.winfo_height(),
            "ad_x": u.ust_ad.winfo_x(),
            "cubuk_y": u.cubuk.winfo_y(), "cubuk_h": u.cubuk.winfo_height(),
            "durum": u.state(),
            "bar": bool(u.ust_bar.winfo_ismapped()),
            "tam": bool(u.attributes("-fullscreen")),
            "mod": u.mod,
            "sayfa": u.aktif_sayfa + 1,
            "odak": str(u.focus_get()),
        }, f)
    u.after(150, bilgi_yaz)             # durum (zoomed) degisimini de izlesin


u.after(600, bilgi_yaz)

# Teshis kaydi: surukleme istekleri ve cozulen tus adlari (fare.py basar).
KAYIT = bilgi_dosyasi + ".kayit"
open(KAYIT, "w").close()


def kaydet(metin):
    import time
    with open(KAYIT, "a", encoding="utf-8") as f:
        f.write(f"{time.perf_counter():.3f} {metin}\n")


_asil_mesaj = u._pencere_mesaji


def _izle_mesaj(isabet, *arg):
    sonuc = _asil_mesaj(isabet, *arg)
    kaydet(f"pencere_mesaji isabet={isabet} tam={u.attributes('-fullscreen')} -> {sonuc}")
    return sonuc


u._pencere_mesaji = _izle_mesaj
_asil_coz = u.tus_adini_coz


def _izle_coz(olay):
    ad = _asil_coz(olay)
    kaydet(f"tus keysym={olay.keysym!r} char={olay.char!r} state={olay.state:#x} -> {ad!r}"
           f" sayac={u.sayac!r} odak={u.focus_get()}")
    return ad


u.tus_adini_coz = _izle_coz
u.after(sure, u.destroy)
u.mainloop()
