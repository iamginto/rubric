# -*- coding: utf-8 -*-
"""Yakinlastirma: tekerlek olaylarinin tek cizimde birlesmesi, imlec / orta
capasi, hassas tekerlek, bekleyen adimin diger komutlarla iliskisi, sure.

    uv run testler\\zoom.py

Gercek fare/klavye kullanmaz; belge, veri ve ayar dizini gecicidir.
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rubric  # noqa: E402
import pymupdf  # noqa: E402

GECICI = tempfile.mkdtemp(prefix="rubric-zoom-")
rubric.veri_dizini = lambda: GECICI
rubric.ayar_dizini = lambda: GECICI
PDF = os.path.join(GECICI, "zoom.pdf")

b = pymupdf.open()
for i in range(600):
    s = b.new_page(width=595, height=842)
    s.insert_text((72, 100), f"sayfa {i + 1}", fontsize=20)
    s.insert_text((72, 140), "the integral of a vector field along a closed curve", fontsize=12)
b.save(PDF)
b.close()

ADIM = rubric.VARSAYILAN_AYAR["yakinlastirma-adimi"]
hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


def belge_noktasi(u, sx, sy):
    """Tuvaldeki (sx, sy) noktasinin altindaki yer: (sayfa, x pt, y pt)."""
    no, fx, fy = u._capa_al(sx, sy)
    w, h = u.sayfa_noktasi(no)
    return no, round(fx * w, 1), round(fy * h, 1)


def ayni_yer(a, b, pay=2.0):
    return a[0] == b[0] and abs(a[1] - b[1]) < pay and abs(a[2] - b[2]) < pay


def tekerlek(u, delta=120, x=300, y=250):
    u.tuval.event_generate("<Control-MouseWheel>", delta=delta, x=x, y=y)


u = rubric.Rubric(PDF)
u.geometry("900x700")
u.update()
u.yenile()
u.update()
u.sayfaya_git(200)
u.update()
u.komutu_isle("zoom 120")
u.update()

print("-- hizli tekerlek: olaylar birikir, tek cizim --")
z0 = u.zoom
once = belge_noktasi(u, 300, 250)
t = time.perf_counter()
for _ in range(6):
    tekerlek(u)
isleyici = time.perf_counter() - t
dogru("olaylar sirasinda cizim yok", u.zoom == z0 and u._hedef_zoom is not None)
u.update()
toplam = time.perf_counter() - t
dogru("6 tik tek seferde uygulandi", abs(u.zoom - z0 * ADIM ** 6) < 1e-9,
      f"z{z0 * 100:.0f}% -> z{u.zoom * 100:.0f}%")
dogru("6 olay + cizim 400 ms'den kisa", toplam < 0.4,
      f"isleyiciler {isleyici * 1000:.1f} ms, toplam {toplam * 1000:.0f} ms")
sonra = belge_noktasi(u, 300, 250)
dogru("imlecin altindaki yer sabit kaldi", ayni_yer(once, sonra), f"{once} -> {sonra}")
dogru("yalnizca gorunen sayfalar islendi", len(u.tuval_ogeleri) <= 2,
      str(sorted(u.tuval_ogeleri)))

print("\n-- komsular zoom durulunca --")
sinir = time.perf_counter() + 1.0
while u._komsu_isi is not None and time.perf_counter() < sinir:
    u.update()
    time.sleep(0.01)
dogru("komsu cizimi calisti", u._komsu_isi is None, str(sorted(u.tuval_ogeleri)))

print("\n-- tus: ekranin ortasi sabit --")
w, h = u.tuval.winfo_width(), u.tuval.winfo_height()
once = belge_noktasi(u, w / 2, h / 2)
u.calistir("uzaklastir")
u.update()
sonra = belge_noktasi(u, w / 2, h / 2)
dogru("uzaklastirinca orta sabit", ayni_yer(once, sonra), f"{once} -> {sonra}")
once = sonra
u.calistir("yakinlastir")
u.update()
dogru("yakinlastirinca orta sabit", ayni_yer(once, belge_noktasi(u, w / 2, h / 2)))

print("\n-- adim olculeri --")
z = u.zoom
tekerlek(u, delta=40)
u.update()
dogru("hassas tekerlek (delta 40) ucte bir adim", abs(u.zoom - z * ADIM ** (1 / 3)) < 1e-9,
      f"x{u.zoom / z:.4f}")
z = u.zoom
u.sayac = "3"
u.calistir("yakinlastir")
u.update()
dogru("3+ uc adim", abs(u.zoom - z * ADIM ** 3) < 1e-9)
for _ in range(80):
    tekerlek(u)
u.update()
dogru("ust sinir asilmadi", u.zoom == u.ayar["en-cok-yakinlastirma"], f"{u.zoom}")

print("\n-- bekleyen adim ve diger komutlar --")
tekerlek(u, delta=-120)
u.calistir("sigdir-genislik")               # ayni olay grubunda
u.update()
dogru("sigdirma bekleyen adimi iptal etti", u.sigdir == "genislik" and u._hedef_zoom is None)
z = u.zoom
tekerlek(u)
u.komutu_isle("zoom 150")
u.update()
dogru(":zoom bekleyen adimi iptal etti", abs(u.zoom - 1.5) < 1e-9, f"{u.zoom}")
tekerlek(u)
u.calistir("dondur")                       # yeniden duzen: adim kaybolmamali
u.update()
dogru("dondurmede bekleyen adim kaybolmadi", abs(u.zoom - 1.5 * ADIM) < 1e-9, f"{u.zoom}")
for _ in range(3):
    u.calistir("dondur")
u.update()

print("\n-- adim suresi (tek tik, olaydan ekrana) --")
sureler = []
for yon in (1, 1, 1, -1, -1, -1):
    t = time.perf_counter()
    tekerlek(u, delta=120 * yon)
    u.update()
    sureler.append((time.perf_counter() - t) * 1000)
print("  ms:", " ".join(f"{s:.0f}" for s in sureler))
dogru("ortalama adim 80 ms'den kisa", sum(sureler) / len(sureler) < 80,
      f"ort {sum(sureler) / len(sureler):.0f} ms")

tekerlek(u)
u.cik()                                    # bekleyen is cikista patlamasin
dogru("cikista bekleyen is kalmadi", u._zoom_isi is None and u._komsu_isi is None)
print("\nHATA SAYISI:", len(hata))
