# -*- coding: utf-8 -*-
"""rubric.py duman testi: mainloop'suz, gercek bir PDF uzerinde."""
import sys, traceback
import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric
import tempfile as _tf
rubric.veri_dizini = (lambda _g=_tf.mkdtemp(prefix="rubric-veri-"): _g)  # oturum/konum gercek durum.json'a yazilmasin

ortak.yalit(rubric)                        # :bmark gercek durum.json'a yazmasin
PDF = ortak.deneme_pdf(40)

hata = []
u = rubric.Rubric(PDF)
u.geometry("1000x760")
u.update()
u.update_idletasks()
u.yenile()
u.update()

print("sayfa sayisi   :", u.belge.page_count)
print("satir sayisi   :", len(u.satirlar))
print("toplam yuks.   :", u.toplam_yukseklik)
print("zoom (genislik):", round(u.zoom, 3))
print("tuvaldeki sayfa:", sorted(u.tuval_ogeleri))

def dene(ad, *ek):
    try:
        u.calistir(ad)
        u.update()
        d = u.durum_degerleri()
        print(f"  {ad:<22} -> s{d['sayfa']}/{d['toplam']} z{d['zoom']}% "
              f"ofset={int(u.ofset())} sutun={u.sutunlar} ters={u.ters}")
    except Exception as e:
        hata.append((ad, e))
        traceback.print_exc()

for ad in ["asagi", "asagi", "yarim-asagi", "sayfa-ileri", "sonraki-sayfa",
           "sonraki-sayfa", "onceki-sayfa", "son-sayfa", "ilk-sayfa",
           "yakinlastir", "uzaklastir", "sigdir-sayfa", "sigdir-genislik",
           "yakinlastirma-sifirla", "dondur", "dondur", "dondur", "dondur",
           "ters-renk", "ters-renk", "cift-sayfa", "cift-sayfa",
           "geri-zipla", "ileri-zipla", "vurguyu-kapat", "durum-cubugu",
           "durum-cubugu"]:
    dene(ad)

# sayi oneki
u.sayac = "7"; dene("sonraki-sayfa")
u.sayac = "3"; dene("son-sayfa")

# arama
print("\n-- arama --")
u.ara("the")
u.update()
print("  bulgu:", len(u.bulgular), "aktif:", u.bulgu_no)
for _ in range(3):
    u.bulguya_git(1); u.update()
print("  n x3 sonrasi:", u.bulgu_no, "sayfa", u.aktif_sayfa + 1)
u.bulguya_git(-1); u.update()
print("  N sonrasi   :", u.bulgu_no)

# isaret + konum imi
print("\n-- isaret / konum --")
u.sayfaya_git(20); u.update()
im = u.konum_imi(); print("  im:", im[0], round(im[1], 3))
u.isaretler["a"] = im
u.sayfaya_git(2); u.update()
u.konum_imine_git(u.isaretler["a"]); u.update()
print("  isarete donus sayfa:", u.aktif_sayfa)

# zoom degisince konum korunuyor mu
onceki = u.konum_imi()
u.calistir("yakinlastir"); u.update()
sonraki = u.konum_imi()
print(f"  zoom oncesi s{onceki[0]} / sonrasi s{sonraki[0]} (ayni olmali)")

# komut satiri
print("\n-- : komutlari --")
for k in ["goto 5", "zoom 150", "set sayfa-arasi 24", "set ters-renk true",
          "set ters-renk false", "map <C-n> sonraki-sayfa", "nohl", "info",
          "bmark deneme", "blist", "rc", "help", "olmayan-komut"]:
    try:
        u.komutu_isle(k); u.update()
        print(f"  :{k:<24} -> {u.durum.cget('text')[:64]}")
    except Exception as e:
        hata.append((k, e)); traceback.print_exc()

# icindekiler
print("\n-- icindekiler --")
u.icindekiler(); u.update()
print("  mod:", u.mod, "girdi:", u.liste.size())
if u.mod == "icindekiler":
    u.paneli_kapat(); u.update()
print("  kapandi, mod:", u.mod)

# durum cubugu bicimi
print("\n-- durum satiri --")
print(" ", u.ayar["durum-bicimi"].format_map(rubric._Esnek(u.durum_degerleri())))

u.cik()
print("\nHATA SAYISI:", len(hata))
for a, e in hata:
    print("  !", a, "->", e)
