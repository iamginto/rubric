# -*- coding: utf-8 -*-
"""Belge listesi ve oturum: <C-Left>/<C-Right>, B paneli, kapatma, sinir,
kapat-ac ile oturumun geri gelmesi, bellekte tek belge.

    uv run testler\\belgeler.py

Gercek fare/klavye kullanmaz; belgeler, veri ve ayar dizini gecicidir.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rubric  # noqa: E402
import pymupdf  # noqa: E402

GECICI = tempfile.mkdtemp(prefix="rubric-belgeler-")
rubric.veri_dizini = lambda: GECICI
rubric.ayar_dizini = lambda: GECICI


def pdf(ad: str, sayfa: int) -> str:
    yol = os.path.join(GECICI, ad)
    b = pymupdf.open()
    for i in range(sayfa):
        b.new_page(width=595, height=842).insert_text((72, 100), f"{ad} {i + 1}", fontsize=20)
    b.save(yol)
    b.close()
    return yol


A, B, C, D = pdf("a.pdf", 30), pdf("b.pdf", 40), pdf("c.pdf", 50), pdf("d.pdf", 20)
hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


def kur(acilacak=None):
    u = rubric.Rubric(acilacak)
    u.geometry("900x700")
    u.update()
    u.yenile()
    u.update()
    return u


def adlar(u):
    return [os.path.basename(y) for y in u.belgeler]


def bakilan(u):
    return os.path.basename(u.pdf_yolu)


print("-- ilk acilis: oturum yok --")
u = kur()
dogru("belge yok, liste bos", u.belge is None and u.belgeler == [])

print("\n-- ust uste ac: a, b, c --")
for y in (A, B, C):
    u.belgeyi_ac(y)
    u.update()
dogru("sira acilis sirasi", adlar(u) == ["a.pdf", "b.pdf", "c.pdf"], str(adlar(u)))
dogru("bakilan c", bakilan(u) == "c.pdf")
dogru("durum cubugunda [3/3]", "[3/3]" in u.durum.cget("text") or
      u.durum_degerleri()["belgeler"] == " [3/3]", u.durum_degerleri()["belgeler"])

print("\n-- <C-Left> / <C-Right> --")
dogru("tuslar bagli", u.tuslar.get("<C-Left>") == "onceki-belge"
      and u.tuslar.get("<C-Right>") == "sonraki-belge")
u.sayfaya_git(17)                           # c'de 18. sayfaya git
u.update()
eski_belge = u.belge
u.calistir("onceki-belge"); u.update()
dogru("<C-Left>: b", bakilan(u) == "b.pdf", bakilan(u))
dogru("eski belge bellekte kapatildi", eski_belge.is_closed)
u.calistir("onceki-belge"); u.update()
dogru("<C-Left>: a", bakilan(u) == "a.pdf", bakilan(u))
u.calistir("onceki-belge"); u.update()
dogru("bastan sona doner: c", bakilan(u) == "c.pdf", bakilan(u))
dogru("c kaldigi sayfada acildi (18)", u.aktif_sayfa == 17, str(u.aktif_sayfa + 1))
u.calistir("sonraki-belge"); u.update()
dogru("<C-Right> sondan basa: a", bakilan(u) == "a.pdf", bakilan(u))
dogru("gezinirken sira degismedi", adlar(u) == ["a.pdf", "b.pdf", "c.pdf"], str(adlar(u)))
u.belgeyi_ac(B); u.update()                 # listede olani yeniden acmak
dogru("var olan belge yeniden eklenmedi", adlar(u) == ["a.pdf", "b.pdf", "c.pdf"])

print("\n-- gercek tus olayi --")
u.tuval.focus_set()
u.tus_geldi(type("O", (), {"keysym": "Right", "char": "", "state": 0x4})())
u.update()
dogru("Ctrl+Right olayi c'ye gecti", bakilan(u) == "c.pdf", bakilan(u))

print("\n-- B paneli --")
u.calistir("belgeler"); u.update()
dogru("panel acik", u.mod == "belgeler" and u.liste.size() == 3)
dogru("bakilan isaretli ve secili", u.liste.get(2).startswith(" > ")
      and u.liste.curselection() == (2,), u.liste.get(2))
print("   |" + "\n   |".join(u.liste.get(0, "end")))
u._panel_satiri_sec(0)
u.panel_sec(); u.update()
dogru("Enter ile a'ya gecildi", bakilan(u) == "a.pdf" and u.mod == "normal", bakilan(u))

print("\n-- kapatma --")
u.calistir("belgeler"); u.update()
u._panel_satiri_sec(1)                      # b (bakilan degil)
u.listeden_belge_kapat(); u.update()
dogru("x: b listeden cikti, bakilan degismedi",
      adlar(u) == ["a.pdf", "c.pdf"] and bakilan(u) == "a.pdf", str(adlar(u)))
dogru("panel yeni listeyle acik", u.mod == "belgeler" and u.liste.size() == 2)
u.paneli_kapat()
u.calistir("belgeyi-kapat"); u.update()     # bakilani kapat: komsusu acilir
dogru("<C-w>: a kapandi, c acildi", adlar(u) == ["c.pdf"] and bakilan(u) == "c.pdf",
      f"{adlar(u)} / {bakilan(u)}")
u.calistir("sonraki-belge"); u.update()
dogru("tek belgede gezinme uyarisi", u.durum.cget("text") == u.m("tek_belge"))
u.calistir("belgeyi-kapat"); u.update()
dogru("son belge kapandi: bos ekran", u.belge is None and u.belgeler == []
      and u.pdf_yolu == "")

print("\n-- q belgeyi kapatir, Q uygulamadan cikar --")
dogru("q -> belgeyi-kapat, Q -> cik", u.tuslar.get("q") == "belgeyi-kapat"
      and u.tuslar.get("Q") == "cik")
for y in (A, B):
    u.belgeyi_ac(y); u.update()
q_olayi = type("O", (), {"keysym": "q", "char": "q", "state": 0})()
u.tus_geldi(q_olayi); u.update()
dogru("q: b kapandi, a acik, uygulama ayakta", adlar(u) == ["a.pdf"] and bakilan(u) == "a.pdf"
      and u.winfo_exists(), f"{adlar(u)} / {bakilan(u)}")
u.tus_geldi(q_olayi); u.update()
dogru("q: son belge de kapandi, uygulama ayakta", u.belge is None and u.winfo_exists())
dogru("son belge iletisi Q'yu hatirlatir",
      u.durum.cget("text") == u.m("son_belge_kapandi", ad="a.pdf", tus="<C-e>"),
      u.durum.cget("text"))
u.tus_geldi(q_olayi); u.update()
dogru("bos ekranda q: uyari, cikis yok", u.durum.cget("text") == u.m("kapatilacak_yok")
      and u.winfo_exists(), u.durum.cget("text"))

print("\n-- sinir (son-belgeler) --")
u.ayar["son-belgeler"] = 3
for y in (A, B, C):
    u.belgeyi_ac(y); u.update()
u.belgeyi_ac(A); u.update()                 # a'ya yeniden bak: en eski goruldu b olur
u.belgeyi_ac(D); u.update()                 # 4. belge: b dusmeli
dogru("en uzun suredir bakilmayan (b) dustu", adlar(u) == ["a.pdf", "c.pdf", "d.pdf"],
      str(adlar(u)))
dogru("uyari gosterildi", "b.pdf" in u.durum.cget("text"), u.durum.cget("text"))
u.ayar["son-belgeler"] = 10

print("\n-- kapat / ac: oturum geri gelir --")
u.belgeyi_ac(C); u.update()
u.sayfaya_git(29); u.update()
kapandi = []
u.cik, eski_cik = (lambda: kapandi.append(1)), u.cik   # Q'nun cik'a gittigini yakala
u.komutlar["cik"] = u.cik
u.tus_geldi(type("O", (), {"keysym": "Q", "char": "Q", "state": 0x1})())
dogru("Q (Shift+q) cik'i cagirdi", kapandi == [1])
eski_cik()
u = kur()
dogru("liste geri geldi", adlar(u) == ["a.pdf", "c.pdf", "d.pdf"], str(adlar(u)))
dogru("son bakilan (c) acildi", bakilan(u) == "c.pdf", bakilan(u))
dogru("kaldigi sayfada (30)", u.aktif_sayfa == 29, str(u.aktif_sayfa + 1))
dogru("bellekte tek belge: digerleri yalnizca yol",
      all(isinstance(y, str) for y in u.belgeler) and isinstance(u.belge, pymupdf.Document))
u.cik()

print("\n-- dosya verilerek acilis: oturuma eklenir --")
u = kur(B)
dogru("b sona eklendi ve acildi", adlar(u) == ["a.pdf", "c.pdf", "d.pdf", "b.pdf"]
      and bakilan(u) == "b.pdf", str(adlar(u)))
u.cik()

print("\n-- silinmis dosya --")
os.remove(D)
u = kur()
dogru("silinen d listeden atildi", "d.pdf" not in adlar(u), str(adlar(u)))
dogru("uyari", u.durum.cget("text") == u.m("oturum_eksik", n=1), u.durum.cget("text"))
u.cik()

print("\n-- oturum kapali --")
with open(os.path.join(GECICI, "rubricrc"), "w", encoding="utf-8") as f:
    f.write("set oturum false\n")
u = kur()
dogru("oturum false: bos acilir", u.belge is None, bakilan(u))
u.cik()

print("\n-- kapanani geri ac (<C-e>) --")
os.remove(os.path.join(GECICI, "rubricrc"))
D = pdf("d.pdf", 20)
u = kur()
u.belgeler, u.kapananlar = [], []
for y in (A, B, C):
    u.belgeyi_ac(y); u.update()
dogru("<C-e> bagli", u.tuslar.get("<C-e>") == "kapanani-ac")
ctrl_shift_t = type("O", (), {"keysym": "e", "char": "\x05", "state": 0x4})()
dogru("Ctrl+E olayi <C-e> adini verir", u.tus_adini_coz(ctrl_shift_t) == "<C-e>")
u.tus_geldi(ctrl_shift_t); u.update()
dogru("yigin bosken uyari", u.durum.cget("text") == u.m("geri_acilacak_yok"), u.durum.cget("text"))

u.belgeyi_ac(B); u.update()
u.sayfaya_git(22); u.update()
u.calistir("yakinlastir"); u.update()
u.calistir("yakinlastir"); u.update()
u.ofset_ata(u.ofset() + 137); u.ciz(); u.update()     # sayfa ortasinda bir yer
konum, zoom = u.konum_imi(), u.zoom
u.tus_geldi(q_olayi); u.update()
dogru("q: b kapandi", adlar(u) == ["a.pdf", "c.pdf"], str(adlar(u)))
dogru("kapat iletisi geri acma tusunu soyler", "<C-e>" in u.durum.cget("text"),
      u.durum.cget("text"))
u.tus_geldi(ctrl_shift_t); u.update()
dogru("b listedeki eski yerine dondu", adlar(u) == ["a.pdf", "b.pdf", "c.pdf"]
      and bakilan(u) == "b.pdf", f"{adlar(u)} / {bakilan(u)}")
k2 = u.konum_imi()
dogru("ayni sayfa ve oran", k2[0] == konum[0] and abs(k2[1] - konum[1]) < 0.01,
      f"{konum} -> {k2}")
dogru("ayni zoom", abs(u.zoom - zoom) < 1e-6, f"{zoom} -> {u.zoom}")
dogru("ileti", u.durum.cget("text") == u.m("geri_acildi", ad="b.pdf"), u.durum.cget("text"))

print("   iki kaza ust uste:")
u.belgeyi_ac(C); u.update()
u.tus_geldi(q_olayi); u.update()            # c kapanir, b acilir
u.tus_geldi(q_olayi); u.update()            # b kapanir, a acilir
dogru("iki q: yalnizca a kaldi", adlar(u) == ["a.pdf"], str(adlar(u)))
u.tus_geldi(ctrl_shift_t); u.update()
dogru("ilk geri acma: son kapanan (b)", bakilan(u) == "b.pdf"
      and u.durum.cget("text") == u.m("geri_acildi_daha", ad="b.pdf", n=1), u.durum.cget("text"))
u.tus_geldi(ctrl_shift_t); u.update()
dogru("ikinci: c, sira bozulmadi", bakilan(u) == "c.pdf"
      and adlar(u) == ["a.pdf", "b.pdf", "c.pdf"], str(adlar(u)))

print("   sinir (kapanan-belgeler 3):")
u.belgeyi_ac(D); u.update()
for _ in range(4):
    u.tus_geldi(q_olayi); u.update()
dogru("dort q: bos ekran, yiginda 3", u.belge is None and len(u.kapananlar) == 3,
      str([os.path.basename(k["yol"]) for k in u.kapananlar]))
for _ in range(4):
    u.tus_geldi(ctrl_shift_t); u.update()
dogru("en eski kapanan (d) geri gelmez", sorted(adlar(u)) == ["a.pdf", "b.pdf", "c.pdf"],
      str(adlar(u)))
dogru("dorduncu basista uyari", u.durum.cget("text") == u.m("geri_acilacak_yok"),
      u.durum.cget("text"))

print("   q sonra Q: yigin oturumla kalir:")
u.belgeyi_ac(B); u.update()
u.sayfaya_git(33); u.update()
u.tus_geldi(q_olayi); u.update()
u.cik()
u = kur()
dogru("b listede yok ama yiginda", "b.pdf" not in adlar(u)
      and os.path.basename(u.kapananlar[-1]["yol"]) == "b.pdf", str(adlar(u)))
u.tus_geldi(ctrl_shift_t); u.update()
dogru("yeniden baslatinca da geri acildi, sayfa 34", bakilan(u) == "b.pdf"
      and u.aktif_sayfa == 33, f"{bakilan(u)} s{u.aktif_sayfa + 1}")

print("   silinmis dosya:")
u.belgeyi_ac(D); u.update()
u.tus_geldi(q_olayi); u.update()
os.remove(D)
u.tus_geldi(ctrl_shift_t); u.update()
dogru("silinmis: hata iletisi, listeye girmedi", "d.pdf" not in adlar(u)
      and u.durum.cget("text") == u.m("bulunamadi", ne=D), u.durum.cget("text"))

print("\n-- ayarlar > geri-acma-siniri (1-10) --")
D = pdf("d.pdf", 20)
u.kapananlar = []
for y in (A, B, C, D):
    u.belgeyi_ac(y); u.update()
for _ in range(3):
    u.tus_geldi(q_olayi); u.update()
dogru("varsayilanla yiginda 3", len(u.kapananlar) == 3)
dogru("ayarlar grubunda", ("ayarlar", ["geri-acma-siniri"]) in rubric.KOMUT_GRUPLARI)
u.calistir("eylemler"); u.update()
u.palet_desen.set(u.ad("geri-acma-siniri")); u.update()
u.palet_calistir(); u.update()
satirlar = list(u.alt_liste.get(0, "end"))
print("   |" + "\n   |".join(satirlar))
dogru("10 secenek, [x] 3'te, imlec 3'te", len(satirlar) == 10 and "[x]" in satirlar[2]
      and u.alt_secim == 2 and u.palet_kip == "sinir", str(u.alt_secim))
u.alt_gez(2); u.alt_onayla(); u.update()
dogru("5 secildi, palet acik", u.ayar["kapanan-belgeler"] == 5 and u.mod == "palet",
      u.durum.cget("text"))
with open(os.path.join(GECICI, "rubricrc"), encoding="utf-8") as f:
    rc = f.read()
dogru("rubricrc'ye kalici", "set kapanan-belgeler 5" in rc)
u.sinir_menusu(); u.update()
u.alt_gez(-10); u.alt_onayla(); u.update()
dogru("1'e dusunce yigin hemen 1", u.ayar["kapanan-belgeler"] == 1 and len(u.kapananlar) == 1,
      str(len(u.kapananlar)))
u.paneli_kapat() if u.mod != "palet" else u.paleti_kapat()
u.yapi.ata("kapanan-belgeler", "50")
dogru("rubricrc'de 50 yazsa da en cok 10", u.ayar["kapanan-belgeler"] == 10,
      str(u.ayar["kapanan-belgeler"]))
u.cik()
u = kur()
dogru("yeniden acilista rubricrc'den 5 degil son secim (1)", u.ayar["kapanan-belgeler"] == 1,
      str(u.ayar["kapanan-belgeler"]))
u.cik()

print("\nHATA SAYISI:", len(hata))
for h in hata:
    print("  !", h)
