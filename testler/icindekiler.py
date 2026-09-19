# -*- coding: utf-8 -*-
"""Icindekiler paneli: acilista dogru basliktan baslama, oklarla / j k ile
oradan devam etme, secileni hatirlama, sayfa degisince yeni yerden baslama.

    uv run testler\\icindekiler.py

Tuslar Tk'nin icinden (event_generate) gercek olay olarak uretilir, yani
listbox'in kendi sinif baglantilari (oklar) da devreye girer. Belge, veri ve
ayar dizini gecicidir.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rubric  # noqa: E402
import pymupdf  # noqa: E402

GECICI = tempfile.mkdtemp(prefix="rubric-icindekiler-")
rubric.veri_dizini = lambda: GECICI
rubric.ayar_dizini = lambda: GECICI
PDF = os.path.join(GECICI, "icindekiler.pdf")

# Ayni sayfada baslayan birden cok alt bolum bilerek var (1.2 / 1.2.1 / 1.2.2,
# 2.2 / 2.3): "o sayfadaki son baslik" kurali burada yanlis satiri secer.
ICINDEKILER = [
    [1, "Bolum 1", 1], [2, "1.1", 2], [2, "1.2", 4], [3, "1.2.1", 4], [3, "1.2.2", 4],
    [2, "1.3", 6], [1, "Bolum 2", 10], [2, "2.1", 10], [2, "2.2", 13], [2, "2.3", 13],
    [1, "Bolum 3", 20], [2, "3.1", 22], [2, "3.2", 25],
]
b = pymupdf.open()
for i in range(30):
    b.new_page(width=595, height=842).insert_text((72, 100), f"sayfa {i + 1}", fontsize=20)
b.set_toc(ICINDEKILER)
b.save(PDF)
b.close()

hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


def tus(u, dizi, kez=1):
    """Gercek tus basisi gibi: odaktaki pencereye olay uretir."""
    for _ in range(kez):
        (u.focus_get() or u.focus_lastfor()).event_generate(dizi)
        u.update()


def secili(u):
    s = u.liste.curselection()
    return ICINDEKILER[s[0]][1] if s else None


u = rubric.Rubric(PDF)
u.geometry("900x700")
u.update()
u.yenile()
u.update()
u.focus_force()
u.tuval.focus_set()
u.update()

print("-- acilis: bulunulan sayfanin basligi --")
tus(u, "<KeyPress-Tab>")
dogru("panel acildi", u.mod == "icindekiler")
dogru("sayfa 1 -> 'Bolum 1'", secili(u) == "Bolum 1", str(secili(u)))

print("\n-- j ile 2.2'ye in, Enter --")
tus(u, "<KeyPress-j>", 8)
dogru("secim 2.2", secili(u) == "2.2", str(secili(u)))
tus(u, "<KeyPress-Return>")
dogru("panel kapandi, sayfa 13", u.mod == "normal" and u.aktif_sayfa == 12,
      f"{u.mod} s{u.aktif_sayfa + 1}")

print("\n-- tekrar Tab: 2.2 hatirlanmali (2.3 ayni sayfada) --")
tus(u, "<KeyPress-Tab>")
dogru("secim 2.2", secili(u) == "2.2", str(secili(u)))
tus(u, "<KeyPress-Down>")
dogru("asagi ok -> 2.3 (basa atmamali)", secili(u) == "2.3", str(secili(u)))
tus(u, "<KeyPress-Down>")
dogru("asagi ok -> Bolum 3", secili(u) == "Bolum 3", str(secili(u)))
tus(u, "<KeyPress-Up>", 2)
dogru("yukari ok x2 -> 2.2", secili(u) == "2.2", str(secili(u)))
tus(u, "<KeyPress-k>")
dogru("k -> 2.1 (oklarla j/k ayni yerden yurur)", secili(u) == "2.1", str(secili(u)))
tus(u, "<KeyPress-Down>")
dogru("asagi ok -> 2.2", secili(u) == "2.2", str(secili(u)))

print("\n-- Tab ile kapat, sayfalar arasi ilerle, Tab --")
tus(u, "<KeyPress-Tab>")
dogru("panel kapandi", u.mod == "normal")
u.sayfaya_git(22)                          # 23. sayfa: 3.1 (s22) ile 3.2 (s25) arasi
u.update()
tus(u, "<KeyPress-Tab>")
dogru("yeni yerden basladi: 3.1", secili(u) == "3.1", f"{secili(u)}  (s{u.aktif_sayfa + 1})")
tus(u, "<KeyPress-Down>")
dogru("asagi ok -> 3.2", secili(u) == "3.2", str(secili(u)))
tus(u, "<KeyPress-Escape>")

print("\n-- ayni sayfadaki alt bolum: 1.2.1'e Enter, Tab --")
tus(u, "<KeyPress-Tab>")
tus(u, "<KeyPress-g>")
dogru("g -> ilk satir", secili(u) == "Bolum 1", str(secili(u)))
tus(u, "<KeyPress-Down>", 3)
dogru("secim 1.2.1", secili(u) == "1.2.1", str(secili(u)))
tus(u, "<KeyPress-Return>")
tus(u, "<KeyPress-Tab>")
dogru("1.2.1 hatirlandi (1.2.2 ayni sayfada)", secili(u) == "1.2.1", str(secili(u)))
tus(u, "<KeyPress-Down>")
dogru("asagi ok -> 1.2.2", secili(u) == "1.2.2", str(secili(u)))
tus(u, "<KeyPress-G>")
dogru("G -> son satir", secili(u) == "3.2", str(secili(u)))
tus(u, "<KeyPress-Up>")
dogru("G'den sonra yukari ok -> 3.1", secili(u) == "3.1", str(secili(u)))
tus(u, "<KeyPress-Escape>")

print("\n-- elle kaydirinca hatirlanan unutulur --")
u.sayfaya_git(5)                           # 6. sayfa: 1.3
u.update()
tus(u, "<KeyPress-Tab>")
dogru("6. sayfada 1.3", secili(u) == "1.3", str(secili(u)))
tus(u, "<KeyPress-Escape>")

u.cik()
print("\nHATA SAYISI:", len(hata))
