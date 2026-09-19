# -*- coding: utf-8 -*-
"""Metin vurgulari: secim, cizim, kalicilik, silme / geri alma, liste, aktarma.

    uv run testler\\vurgu.py

Gercek fare/klavye KULLANMAZ: olaylar Tk'nin icinden (event_generate) uretilir.
Icerigi bilinen gecici bir PDF uretir; veri ve ayar dizini de gecicidir.
"""
import hashlib
import os
import sys
import tempfile

import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric
import pymupdf

GECICI = tempfile.mkdtemp(prefix="rubric-vurgu-")
rubric.veri_dizini = lambda: GECICI
rubric.ayar_dizini = lambda: GECICI
PDF = os.path.join(GECICI, "deneme.pdf")

# Bilinen metinli iki sayfalik belge
b = pymupdf.open()
for s in range(2):
    sayfa = b.new_page(width=595, height=842)
    sayfa.insert_text((72, 100), "alfa beta gama delta epsilon", fontsize=14)
    sayfa.insert_text((72, 130), "zeta eta teta iota kappa", fontsize=14)
    sayfa.insert_text((72, 160), f"sayfa {s + 1} son satir", fontsize=14)
b.save(PDF)
b.close()
OZET = hashlib.sha256(open(PDF, "rb").read()).hexdigest()

hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


def kelime_merkezi(u, no, kelime):
    """Kelimenin tuvaldeki merkezi, widget koordinatinda (event_generate icin)."""
    for k in u.belge[no].get_text("words"):
        if k[4] == kelime:
            yer = u.sayfa_yeri(no)
            x0, y0, x1, y1 = u.aygit_dikdortgeni(no, pymupdf.Rect(k[:4]), yer)
            return (int((x0 + x1) / 2 - u.tuval.canvasx(0)),
                    int((y0 + y1) / 2 - u.tuval.canvasy(0)))
    raise KeyError(kelime)


def surukle(u, a, b, durum=0):
    t = u.tuval
    t.event_generate("<ButtonPress-1>", x=a[0], y=a[1], state=durum)
    for i in range(1, 6):
        t.event_generate("<B1-Motion>", x=a[0] + (b[0] - a[0]) * i // 5,
                         y=a[1] + (b[1] - a[1]) * i // 5, state=durum | 0x100)
    t.event_generate("<ButtonRelease-1>", x=b[0], y=b[1], state=durum | 0x100)
    u.update()


def piksel(u, no, kelime):
    """Kelimenin ortasindaki islenmis sayfa pikseli (r, g, b)."""
    u.update()
    resim = u.sayfa_resmi(no)
    for k in u.belge[no].get_text("words"):
        if k[4] == kelime:
            d = pymupdf.Rect(k[:4]) * u.sayfa_matrisi()
            sinir = u.belge[no].rect * u.sayfa_matrisi()
            x = int((d.x0 + d.x1) / 2 - sinir.x0)
            y = int(d.y0 - sinir.y0 + 2)            # harfin ustu: zemin rengi
            return resim.get(x, y)
    raise KeyError(kelime)


def sari_mi(rgb):
    r, g, b_ = rgb
    return r > 200 and g > 170 and b_ < 140


u = rubric.Rubric(PDF)
u.geometry("900x700")
u.update()
u.yenile()
u.update()

print("-- normal surukleme vurgulamaz, kaydirir --")
surukle(u, kelime_merkezi(u, 0, "alfa"), kelime_merkezi(u, 0, "delta"))
dogru("vurgu yok", u.vurgular == [])

print("\n-- Shift+surukle --")
surukle(u, kelime_merkezi(u, 0, "beta"), kelime_merkezi(u, 0, "delta"), durum=0x1)
dogru("bir vurgu", len(u.vurgular) == 1)
if u.vurgular:
    v = u.vurgular[0]
    dogru("metin 'beta gama delta'", v["metin"] == "beta gama delta", repr(v["metin"]))
    dogru("tek satir tek dikdortgen", len(v["dikler"]) == 1)
dogru("vurgulanan kelime sari cizildi", sari_mi(piksel(u, 0, "gama")), str(piksel(u, 0, "gama")))
dogru("disindaki kelime beyaz kaldi", not sari_mi(piksel(u, 0, "alfa")), str(piksel(u, 0, "alfa")))
dogru("durum.json'a hemen yazildi",
      '"beta gama delta"' in open(os.path.join(GECICI, "durum.json"), encoding="utf-8").read())

print("\n-- kalem: tik vurgulamaz, iki satir surukle --")
u.calistir("vurgu-kalemi")
dogru("kalem acik", u.kalem and u.durum_degerleri()["mod"] == u.m("mod_kalem"))
a = kelime_merkezi(u, 0, "epsilon")
surukle(u, a, a)
dogru("kipirdamayan tik vurgu eklemedi", len(u.vurgular) == 1)
surukle(u, kelime_merkezi(u, 0, "epsilon"), kelime_merkezi(u, 0, "eta"))
dogru("ikinci vurgu", len(u.vurgular) == 2)
if len(u.vurgular) == 2:
    v2 = u.vurgular[1]
    dogru("satir asan secim: 2 dikdortgen", len(v2["dikler"]) == 2, str(len(v2["dikler"])))
    dogru("metin 'epsilon zeta eta'", v2["metin"] == "epsilon zeta eta", repr(v2["metin"]))
u.calistir("vurguyu-kapat")                     # Esc
dogru("Esc kalemi birakti", not u.kalem)
dogru("Esc vurgulara dokunmadi", len(u.vurgular) == 2)

print("\n-- sag tik sil, u geri al --")
x, y = kelime_merkezi(u, 0, "gama")
u.tuval.event_generate("<Button-3>", x=x, y=y)
u.update()
dogru("sag tik sildi", len(u.vurgular) == 1 and u.vurgular[0]["metin"] == "epsilon zeta eta")
dogru("silinince beyaza dondu", not sari_mi(piksel(u, 0, "gama")))
u.calistir("vurgu-geri-al")
dogru("u silineni geri getirdi", len(u.vurgular) == 2)
dogru("geri gelen yine sari", sari_mi(piksel(u, 0, "gama")))
u.calistir("vurgu-geri-al")
dogru("u bir daha: geri getirmeyi geri aldi", len(u.vurgular) == 1)
u.calistir("vurgu-geri-al")
u.calistir("vurgu-geri-al")
u.calistir("vurgu-geri-al")
dogru("gecmis bitince sessizce durur", len(u.vurgular) == 0)
surukle(u, kelime_merkezi(u, 0, "beta"), kelime_merkezi(u, 0, "delta"), durum=0x1)
surukle(u, kelime_merkezi(u, 0, "zeta"), kelime_merkezi(u, 0, "iota"), durum=0x1)
dogru("iki vurgu yeniden", len(u.vurgular) == 2)

print("\n-- dondurulmus sayfada secim --")
u.calistir("dondur")
u.update()
surukle(u, kelime_merkezi(u, 0, "sayfa"), kelime_merkezi(u, 0, "satir"), durum=0x1)
dogru("90 derecede dogru kelimeler", u.vurgular[-1]["metin"] == "sayfa 1 son satir",
      repr(u.vurgular[-1]["metin"]))
for _ in range(3):
    u.calistir("dondur")
u.update()
dogru("uc vurgu", len(u.vurgular) == 3)

print("\n-- gece modu --")
u.calistir("ters-renk")
u.update()
dogru("gece modunda cizim hatasiz", u.sayfa_resmi(0) is not None)
u.calistir("ters-renk")

print("\n-- liste (V) --")
u.calistir("vurgular")
u.update()
dogru("panel acik", u.mod == "vurgular" and u.liste.size() == 3, f"{u.mod} {u.liste.size()}")
for i in range(u.liste.size()):
    print("   |" + u.liste.get(i))
class Tus:
    """Panel tus isleyicisine dogrudan verilen olay. event_generate ile klavye
    olayi yalnizca pencere isletim sisteminde odaktaysa ulasir; test penceresi
    arkada kalinca kaybolur. Pencereyi zorla one almak kullaniciyi boler."""
    def __init__(self, keysym, char=""):
        self.keysym, self.char, self.state = keysym, char, 0


u.liste.selection_clear(0, "end")
u.liste.selection_set(0)
u.panel_tus(Tus("x", "x"))
u.update()
dogru("x listeden sildi", len(u.vurgular) == 2 and u.liste.size() == 2)
u.liste.selection_clear(0, "end")
u.liste.selection_set(1)
u.panel_tus(Tus("Return", "\r"))
u.update()
dogru("Enter panele kapatti", u.mod == "normal")
u.calistir("vurgu-geri-al")
dogru("listeden silinen de geri alinir", len(u.vurgular) == 3)

print("\n-- kalicilik: yeniden ac --")
u.cik()
u = rubric.Rubric(PDF)
u.geometry("900x700")
u.update()
u.yenile()
u.update()
dogru("uc vurgu geri yuklendi", len(u.vurgular) == 3)
dogru("yeniden acilista sari", sari_mi(piksel(u, 0, "gama")))

print("\n-- renk degisimi --")
u.komutu_isle("set vurgu-rengi #66ff66")
u.update()
r, g, b_ = piksel(u, 0, "gama")
dogru("yeni renk (yesil) uygulandi", g > 200 and r < 160, str((r, g, b_)))
u.komutu_isle("set vurgu-rengi #ffd54a")

print("\n-- vurgulu kopya PDF --")
u.calistir("vurgulari-aktar")
EK = u.m("vurgulu_ek")                      # dile gore: highlighted / vurgulu / markiert
hedef = os.path.join(GECICI, f"deneme-{EK}.pdf")
dogru("kopya yazildi", os.path.exists(hedef), hedef)
if os.path.exists(hedef):
    k = pymupdf.open(hedef)
    notlar = [a for s in k for a in s.annots()]
    dogru("kopyada 3 highlight notu", len(notlar) == 3, str(len(notlar)))
    dogru("notun yazari 'rubric', icerigi metin",
          any(a.info.get("title") == "rubric" and a.info.get("content") == "beta gama delta"
              for a in notlar))
    k.close()
u.calistir("vurgulari-aktar")
dogru("ikinci aktarma ustune yazmadi", os.path.exists(os.path.join(GECICI, f"deneme-{EK}-2.pdf")))
dogru("ORIJINAL PDF DEGISMEDI",
      hashlib.sha256(open(PDF, "rb").read()).hexdigest() == OZET)
dogru("orijinalde hic not yok", not any(True for s in pymupdf.open(PDF) for _ in s.annots()))

u.cik()
print("\nHATA SAYISI:", len(hata))
