# -*- coding: utf-8 -*-
"""Sayi + Enter ile sayfaya gitme: 5<Return> -> 5. sayfa."""
import sys
import tempfile
import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric

# Kalinan sayfa durum.json'a yazilir; testin zıplamalari gercek okuma yerini
# ezmesin diye veri ve ayar dizini gecici bir dizine cevrilir.
GECICI = tempfile.mkdtemp(prefix="rubric-sayfa-")
rubric.veri_dizini = lambda: GECICI
rubric.ayar_dizini = lambda: GECICI

PDF = ortak.deneme_pdf(40)

hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


def tus(pencere, dizi):
    (pencere.focus_get() or pencere.focus_lastfor()).event_generate(dizi)
    pencere.update()


def yaz(pencere, metin):
    for harf in metin:
        tus(pencere, f"<KeyPress-{harf}>")
    tus(pencere, "<KeyPress-Return>")


u = rubric.Rubric(PDF)
u.geometry("1000x760")
u.update()
u.yenile()
u.update()
u.tuval.focus_set()
u.update()
toplam = u.belge.page_count

yaz(u, "12")
dogru("12<Return> -> 12. sayfa", u.aktif_sayfa == 11, f"sayfa {u.aktif_sayfa + 1}")
dogru("sayac temizlendi", u.sayac == "")

yaz(u, "3")
dogru("3<Return> -> 3. sayfa", u.aktif_sayfa == 2, f"sayfa {u.aktif_sayfa + 1}")

yaz(u, "999999")
dogru("fazlasi son sayfaya", u.aktif_sayfa == toplam - 1,
      f"sayfa {u.aktif_sayfa + 1}/{toplam}")

tus(u, "<KeyPress-Return>")                 # sayisiz Enter bir sey yapmamali
dogru("sayisiz Enter yerinde", u.aktif_sayfa == toplam - 1)

tus(u, "<KeyPress-4>")
tus(u, "<KeyPress-Escape>")                 # vazgec
dogru("Esc sayaci sildi", u.sayac == "")

u.cik()
print("\nHATA SAYISI:", len(hata))
