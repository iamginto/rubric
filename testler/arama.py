# -*- coding: utf-8 -*-
"""Parcali aramanin olcumu: ilk eslemeye varis suresi ve donma."""
import sys, time
import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric
import tempfile as _tf
rubric.veri_dizini = (lambda _g=_tf.mkdtemp(prefix="rubric-veri-"): _g)  # oturum/konum gercek durum.json'a yazilmasin

ortak.yalit(rubric)                        # gercek durum.json'a yazmasin
PDF = ortak.deneme_pdf(1612)
u = rubric.Rubric(PDF)
u.geometry("1000x760")
u.update(); u.yenile(); u.update()

# Belgenin ortasinda dur; arama imlecten baslamali.
u.sayfaya_git(800); u.update()
print("baslangic sayfasi:", u.aktif_sayfa + 1)

t0 = time.perf_counter()
u.ara("integral")
u.update()                       # ilk parti islendi
ilk = time.perf_counter() - t0
print(f"ilk esleme        : {ilk*1000:.0f} ms -> sayfa {u.aktif_sayfa+1}, "
      f"{len(u.bulgular)} esleme (tarama surerken)")

# Tarama surerken arayuz yanit veriyor mu: j'ye basmayi dene
t0 = time.perf_counter()
u.calistir("asagi"); u.update()
print(f"tarama surerken j : {(time.perf_counter()-t0)*1000:.0f} ms (donma yok demek)")

# Taramanin bitmesini bekle, gecen sureyi ve toplami olc
t0 = time.perf_counter()
sinir = time.perf_counter() + 60
while u.arama_kuyrugu and time.perf_counter() < sinir:
    u.update()
print(f"tarama tamamlandi : {time.perf_counter()-t0:.1f} sn, toplam {len(u.bulgular)} esleme")

# n / N sirali mi
onceki = None
sirali = True
for _ in range(6):
    u.bulguya_git(1); u.update()
    s = u.bulgular[u.bulgu_no][0]
    if onceki is not None and s < onceki:
        pass  # listenin sonundan basa sarmasi normal
    onceki = s
print("n x6 sonrasi sayfa:", u.bulgular[u.bulgu_no][0] + 1, "indeks", u.bulgu_no)
u.bulguya_git(-1); u.update()
print("N sonrasi indeks  :", u.bulgu_no)

# liste belge sirasinda mi
sayfalar = [b[0] for b in u.bulgular]
print("bulgu listesi sirali mi:", sayfalar == sorted(sayfalar))

# yeni arama eskisini kesiyor mu
u.ara("matrix")
u.update()
kimlik = u.arama_kimlik
u.ara("vector")
u.update()
print("yeni arama eskisini kesti:", u.arama_kimlik > kimlik, "| desen:", u.son_desen)
u.vurguyu_kapat(); u.update()
print("nohl sonrasi bulgu:", len(u.bulgular), "kuyruk:", len(u.arama_kuyrugu))

u.cik()
print("\nbitti")
