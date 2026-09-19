# -*- coding: utf-8 -*-
"""1612 sayfalik belgede acilis, kaydirma ve icindekiler olcumu."""
import sys, time, traceback
import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric
import tempfile as _tf
rubric.veri_dizini = (lambda _g=_tf.mkdtemp(prefix="rubric-veri-"): _g)  # oturum/konum gercek durum.json'a yazilmasin

ortak.yalit(rubric)                        # kalinan yer gercek durum.json'a yazilmasin
PDF = ortak.deneme_pdf(1612)

t0 = time.perf_counter()
u = rubric.Rubric(PDF)
u.geometry("1000x760")
u.update(); u.yenile(); u.update()
print(f"acilis            : {time.perf_counter()-t0:.2f} sn  ({u.belge.page_count} sayfa)")
print(f"toplam yukseklik  : {u.toplam_yukseklik} px, zoom {u.zoom:.2f}")

t0 = time.perf_counter()
u.duzeni_hesapla()
print(f"duzen hesabi      : {time.perf_counter()-t0*0:.4f}".ljust(1), end="")
t1 = time.perf_counter(); u.duzeni_hesapla(); print(f"\rduzen hesabi      : {time.perf_counter()-t1:.3f} sn")

# 60 kez j (tipik kaydirma dongusu)
t0 = time.perf_counter()
for _ in range(60):
    u.calistir("asagi"); u.update()
print(f"60x j             : {time.perf_counter()-t0:.2f} sn  -> sayfa {u.aktif_sayfa+1}")

t0 = time.perf_counter()
for _ in range(10):
    u.calistir("sayfa-ileri"); u.update()
print(f"10x <Space>       : {time.perf_counter()-t0:.2f} sn  -> sayfa {u.aktif_sayfa+1}")

t0 = time.perf_counter()
u.calistir("son-sayfa"); u.update()
print(f"G (son sayfa)     : {time.perf_counter()-t0:.2f} sn  -> sayfa {u.aktif_sayfa+1}")

t0 = time.perf_counter()
u.calistir("yakinlastir"); u.update()
print(f"yakinlastir       : {time.perf_counter()-t0:.2f} sn  -> z{int(u.zoom*100)}%")

t0 = time.perf_counter()
u.calistir("cift-sayfa"); u.update()
print(f"cift sayfa        : {time.perf_counter()-t0:.2f} sn  -> {len(u.satirlar)} satir")
u.calistir("cift-sayfa"); u.update()

# icindekiler
print("\n-- icindekiler --")
t0 = time.perf_counter()
u.icindekiler(); u.update()
print(f"acilis            : {time.perf_counter()-t0:.2f} sn, mod={u.mod}, girdi={u.liste.size()}")
print("  ilk 4 satir:")
for i in range(min(4, u.liste.size())):
    print("   ", u.liste.get(i)[:70])
secili = u.liste.curselection()
print("  aktif sayfaya gore secim:", secili)
u.panel_gez(1); u.panel_gez(1); u.update()
print("  j j sonrasi secim:", u.liste.curselection())
u.liste.selection_clear(0, "end"); u.liste.selection_set(10)
u.panel_sec(); u.update()
print(f"  10. basliga gidildi -> sayfa {u.aktif_sayfa+1}, mod={u.mod}")

# arama (buyuk belge)
print("\n-- arama (1612 sayfa) --")
t0 = time.perf_counter()
u.ara("integral")
u.update()
print(f"  'integral' : {len(u.bulgular)} esleme, {time.perf_counter()-t0:.2f} sn")

# bellek: onbellek siniri tutuyor mu
print("\nonbellekteki sayfa:", len(u.onbellek), "/ sinir", u.ayar["onbellek"])
print("tuvaldeki sayfa   :", len(u.tuval_ogeleri))

u.cik()
print("\nbitti, hata yok")
