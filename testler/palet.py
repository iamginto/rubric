# -*- coding: utf-8 -*-
"""Eylem paletini (<C-k>) mainloop'suz surer: gezinme, tus atama, rubricrc.

rubricrc gercek yoluna degil, gecici bir dizine yazilir: `ayar_dizini` testte
degistirilir. Boylece kullanicinin kendi yapilandirmasina dokunulmaz.
"""
import os
import sys
import tempfile
import traceback

import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric
import tempfile as _tf
rubric.veri_dizini = (lambda _g=_tf.mkdtemp(prefix="rubric-veri-"): _g)  # oturum/konum gercek durum.json'a yazilmasin

GECICI = tempfile.mkdtemp(prefix="rubric-palet-")
rubric.ayar_dizini = lambda: GECICI
RC = os.path.join(GECICI, "rubricrc")

hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


def tus(pencere, dizi):
    """Gercek tus basisi gibi: odaktaki pencereye olay uretir."""
    # Pencere onde degilken focus_get() None doner; son odaklanan widget'a yolla.
    (pencere.focus_get() or pencere.focus_lastfor()).event_generate(dizi)
    pencere.update()


u = rubric.Rubric()
u.geometry("1000x760")
u.update()
u.update_idletasks()

print("-- tus adi cozumu --")


class _Olay:
    def __init__(self, keysym, char="", state=0):
        self.keysym, self.char, self.state = keysym, char, state


for keysym, char, state, beklenen in [
    ("k", "k", 0x0, "k"),
    ("k", "", 0x4, "<C-k>"),
    ("k", "", 0x20000, "<A-k>"),
    ("K", "K", 0x1, "K"),
    ("k", "", 0x5, "<C-S-k>"),
    ("F5", "", 0x0, "<F5>"),
    ("F5", "", 0x1, "<S-F5>"),
    ("Left", "", 0x4, "<C-Left>"),
    ("Escape", "", 0x0, "<Esc>"),
    ("space", " ", 0x0, "<Space>"),
    ("Control_L", "", 0x4, ""),
    ("e", "e", 0x20004, "e"),          # AltGr: bileske degil, harf
]:
    cikan = u.tus_adini_coz(_Olay(keysym, char, state))
    dogru(f"{keysym!r} state={hex(state)} -> {cikan!r}", cikan == beklenen,
          f"beklenen {beklenen!r}")

print("\n-- palet acilisi --")
tus(u, "<Control-KeyPress-k>")
dogru("mod palet", u.mod == "palet")
dogru("palet gorunur", bool(u.palet.winfo_ismapped()))
dogru("odak arama satirinda", u.focus_get() is u.palet_girdi)
dogru("liste doldu", u.palet_liste.size() > 30, f"{u.palet_liste.size()} satir")
dogru("grup basligi secili degil", u.palet_secili() is not None,
      f"secili: {u.palet_secili()}")
print("  ilk satirlar:")
for i in range(4):
    print("   |" + u.palet_liste.get(i))

print("\n-- gezinme --")
ilk = u.palet_secili()
tus(u, "<KeyPress-Down>")
dogru("asagi secim degistirdi", u.palet_secili() != ilk,
      f"{ilk} -> {u.palet_secili()}")
tus(u, "<KeyPress-Up>")
dogru("yukari geri getirdi", u.palet_secili() == ilk)

print("\n-- suzme --")
for harf in "gece":
    tus(u, f"<KeyPress-{harf}>")
dogru("desen yazildi", u.palet_desen.get() == "gece", repr(u.palet_desen.get()))
dogru("ters-renk suzuldu", u.palet_secili() == "ters-renk", str(u.palet_secili()))
dogru("liste kisaldi", u.palet_liste.size() < 6, f"{u.palet_liste.size()} satir")
print("   |" + u.palet_liste.get(u.palet_secim))

print("\n-- eylem menusu --")
tus(u, "<Control-KeyPress-k>")
dogru("kip eylem", u.palet_kip == "eylem")
dogru("menu gorunur", bool(u.alt_menu.winfo_ismapped()))
dogru("hedef ters-renk", u.palet_hedef == "ters-renk")
for i in range(u.alt_liste.size()):
    print("   |" + u.alt_liste.get(i))
dogru("secenekler", u.alt_ogeleri == ["calistir", "tus-ata", "tus-kaldir"],
      str(u.alt_ogeleri))

print("\n-- tus ata --")
tus(u, "<KeyPress-j>")                      # eylem menusunde j = asagi
dogru("menude gezindi", u.alt_secim == 1)
tus(u, "<KeyPress-Return>")
dogru("kip yakala", u.palet_kip == "yakala")
dogru("yakalama ekrani gorunur", bool(u.yakala.winfo_ismapped()))
print("   |", u.yakala_ust.cget("text"), "|", u.yakala_alt.cget("text"))

tus(u, "<KeyPress-Control_L>")              # salt degistirici yutulmali
dogru("salt Ctrl yakalamayi bitirmedi", u.palet_kip == "yakala")

tus(u, "<Control-Alt-KeyPress-n>")
dogru("kip onay", u.palet_kip == "onay")
dogru("yakalanan tus", u.palet_yeni_tus == "<C-A-n>", u.palet_yeni_tus)
tus(u, "<Control-KeyPress-r>")              # fikir degistir: <C-r> zaten bunun
dogru("yeni tus ustune yazildi", u.palet_yeni_tus == "<C-r>", u.palet_yeni_tus)
dogru("'zaten bagli' uyarisi", u.yakala_orta.cget("text") == u.m("zaten_bagli", tus="<C-r>"),
      u.yakala_orta.cget("text"))
tus(u, "<Control-KeyPress-d>")              # <C-d> baska komutun: catisma
dogru("catisma uyarisi", u.ad("yarim-asagi") in u.yakala_orta.cget("text"),
      u.yakala_orta.cget("text"))
tus(u, "<KeyPress-5>")                      # sayi tusu uyarisi
dogru("sayi tusu uyarisi", u.yakala_orta.cget("text") == u.m("sayi_tusu"),
      u.yakala_orta.cget("text"))
tus(u, "<Control-KeyPress-n>")
dogru("son aday <C-n>", u.palet_yeni_tus == "<C-n>", u.palet_yeni_tus)

tus(u, "<KeyPress-Return>")
dogru("atama uygulandi", u.tuslar.get("<C-n>") == "ters-renk",
      str(u.tuslar.get("<C-n>")))
dogru("kip listeye dondu", u.palet_kip == "liste")
dogru("secim komutta kaldi", u.palet_secili() == "ters-renk")
dogru("rubricrc yazildi", os.path.exists(RC))
print("  --- rubricrc ---")
icerik = open(RC, encoding="utf-8").read()
print("  " + icerik.replace("\n", "\n  ").rstrip())
dogru("blokta map satiri", "map <C-n> ters-renk" in icerik)
dogru("varsayilan tus blokta degil", "map <C-r>" not in icerik)

print("\n-- atanan tus gercekten calisiyor mu --")
u.paleti_kapat()
onceki = u.ters
tus(u, "<Control-KeyPress-n>")
dogru("<C-n> gece modunu cevirdi", u.ters != onceki, f"{onceki} -> {u.ters}")
tus(u, "<Control-KeyPress-n>")

print("\n-- tusu kaldir (tek tus) --")
tus(u, "<Control-KeyPress-k>")
for harf in "gece":
    tus(u, f"<KeyPress-{harf}>")
tus(u, "<Control-KeyPress-k>")
dogru("dort secenek (varsayilandan sapti)",
      u.alt_ogeleri == ["calistir", "tus-ata", "tus-kaldir", "varsayilan"],
      str(u.alt_ogeleri))
tus(u, "<KeyPress-j>")
tus(u, "<KeyPress-j>")
tus(u, "<KeyPress-Return>")                 # tusu kaldir -> iki tus var, secmeli
dogru("kip kaldir", u.palet_kip == "kaldir", u.palet_kip)
dogru("iki aday", u.alt_ogeleri == ["<C-n>", "<C-r>"], str(u.alt_ogeleri))
tus(u, "<KeyPress-Return>")                 # ilkini kaldir: <C-n>
dogru("<C-n> kalkti", "<C-n>" not in u.tuslar)
dogru("<C-r> duruyor", u.tuslar.get("<C-r>") == "ters-renk")
icerik = open(RC, encoding="utf-8").read()
dogru("map satiri rubricrc'den silindi", "map <C-n>" not in icerik)
dogru("gereksiz unmap yazilmadi", "unmap" not in icerik)

print("\n-- varsayilan tusu kaldir ve geri getir --")
tus(u, "<Control-KeyPress-k>")
dogru("eylem menusu", u.palet_kip == "eylem", u.palet_kip)
tus(u, "<KeyPress-j>")
tus(u, "<KeyPress-j>")
tus(u, "<KeyPress-Return>")                 # tek tus kaldi: dogrudan kalkar
dogru("<C-r> kalkti", "<C-r>" not in u.tuslar)
icerik = open(RC, encoding="utf-8").read()
dogru("unmap yazildi", "unmap <C-r>" in icerik)
tus(u, "<Control-KeyPress-k>")
dogru("varsayilana don gorunuyor", "varsayilan" in u.alt_ogeleri, str(u.alt_ogeleri))
for _ in range(u.alt_ogeleri.index("varsayilan")):
    tus(u, "<KeyPress-j>")
tus(u, "<KeyPress-Return>")
dogru("<C-r> geri geldi", u.tuslar.get("<C-r>") == "ters-renk")
icerik = open(RC, encoding="utf-8").read()
dogru("unmap silindi", "unmap <C-r>" not in icerik)

print("\n-- elle yazilan satirlar korunuyor mu --")
u.paleti_kapat()
with open(RC, encoding="utf-8") as f:
    eski = f.read()
with open(RC, "w", encoding="utf-8") as f:
    f.write("# kullanicinin kendi satiri\nset sayfa-arasi 24\nmap w sigdir-genislik\n"
            + eski.split("# rubric yapilandirmasi")[0])
u.palet_hedef = "sunum"
dogru("yazma basarili", u.rc_tus_yaz({"<F9>": "sunum"}))
icerik = open(RC, encoding="utf-8").read()
dogru("kullanici satiri duruyor", "set sayfa-arasi 24" in icerik)
dogru("kullanici map'i duruyor", "map w sigdir-genislik" in icerik)
dogru("yeni atama blokta", "map <F9> sunum" in icerik)
print("  --- rubricrc ---")
print("  " + icerik.replace("\n", "\n  ").rstrip())

print("\n-- yakalamadan esc ile cikis --")
tus(u, "<Control-KeyPress-k>")
for harf in "sunum":
    tus(u, f"<KeyPress-{harf}>")
dogru("sunum suzuldu", u.palet_secili() == "sunum", str(u.palet_secili()))
tus(u, "<Control-KeyPress-k>")
tus(u, "<KeyPress-j>")
tus(u, "<KeyPress-Return>")
tus(u, "<Control-KeyPress-y>")
dogru("aday alindi", u.palet_yeni_tus == "<C-y>", u.palet_yeni_tus)
tus(u, "<KeyPress-Escape>")
dogru("iptal: kip liste", u.palet_kip == "liste")
dogru("iptal: atama yapilmadi", "<C-y>" not in u.tuslar)
dogru("iptal: palet acik kaldi", u.mod == "palet")
tus(u, "<KeyPress-Escape>")

print("\n-- palet esc ile kapaniyor --")
tus(u, "<Control-KeyPress-k>")
tus(u, "<KeyPress-Escape>")
dogru("mod normal", u.mod == "normal")
dogru("palet gizlendi", not u.palet.winfo_ismapped())
dogru("odak tuvalde", u.focus_get() is u.tuval)

print("\n-- eslesmeyen desen --")
tus(u, "<Control-KeyPress-k>")
for harf in "zzz":
    tus(u, f"<KeyPress-{harf}>")
dogru("eslesme yok satiri", u.palet_liste.size() == 1, u.palet_liste.get(0))
dogru("secili komut yok", u.palet_secili() is None)
tus(u, "<Control-KeyPress-k>")               # bos listede eylem menusu acilmamali
dogru("bos listede menu acilmadi", u.palet_kip == "liste")
tus(u, "<KeyPress-Return>")                  # calistirilacak sey yok
dogru("bos listede enter zarar vermedi", u.mod == "palet")
tus(u, "<KeyPress-Escape>")

print("\n-- paleti acan son tus korunuyor --")
tus(u, "<Control-KeyPress-k>")
for harf in "eylemler":
    tus(u, f"<KeyPress-{harf}>")
dogru("eylemler suzuldu", u.palet_secili() == "eylemler", str(u.palet_secili()))
tus(u, "<Control-KeyPress-k>")
dogru("tusu kaldir secenegi var", "tus-kaldir" in u.alt_ogeleri, str(u.alt_ogeleri))
for _ in range(u.alt_ogeleri.index("tus-kaldir")):
    tus(u, "<KeyPress-j>")
tus(u, "<KeyPress-Return>")
dogru("<C-k> kaldirilamadi", u.tuslar.get("<C-k>") == "eylemler")
dogru("rubricrc'ye unmap <C-k> yazilmadi",
      "unmap <C-k>" not in open(RC, encoding="utf-8").read())
tus(u, "<KeyPress-Escape>")
dogru("palet hala <C-k> ile aciliyor", u.mod == "normal")
tus(u, "<Control-KeyPress-k>")
dogru("  ...acildi", u.mod == "palet")
for harf in "sunum":
    tus(u, f"<KeyPress-{harf}>")
tus(u, "<Control-KeyPress-k>")
tus(u, "<KeyPress-j>")
tus(u, "<KeyPress-Return>")                 # sunum'a tus ata
tus(u, "<Control-KeyPress-k>")
dogru("kilit uyarisi", u.yakala_orta.cget("text") == u.m("kilit_uyari", tus="<C-k>"),
      u.yakala_orta.cget("text"))
tus(u, "<KeyPress-Return>")
dogru("<C-k> baska komuta alinamadi", u.tuslar.get("<C-k>") == "eylemler")
dogru("onay ekraninda kaldi", u.palet_kip == "onay", u.palet_kip)
tus(u, "<KeyPress-Escape>")
tus(u, "<KeyPress-Escape>")

print("\n-- dil --")
dogru("varsayilan dil ingilizce", u.ayar["dil"] == "en", u.ayar["dil"])
tus(u, "<Control-KeyPress-k>")
dogru("ingilizce grup basligi", " [ navigation ]" in u.palet_liste.get(0, "end"))
dogru("ingilizce ipucu", u.palet_ipucu.cget("text") == rubric.ceviri("en", "ipucu_liste"))
# "i" event_generate ile Tk'ye ulasmiyor (Windows); desen dogrudan yazilir.
u.palet_desen.set("dil"); u.update()
dogru("dil komutu suzuldu", u.palet_secili() == "dil", str(u.palet_secili()))
dogru("ingilizce komut adi", any(s.startswith("  language ") for s in u.palet_liste.get(0, "end")))
tus(u, "<KeyPress-Return>")                 # dil listesi acilir, hemen degismez
dogru("enter secim listesini acti", u.palet_kip == "dil" and u.mod == "palet", u.palet_kip)
dogru("uc dil listelendi", u.alt_ogeleri == ["en", "tr", "de"], str(u.alt_ogeleri))
dogru("secili dil isaretli", u.alt_liste.get(0).strip().startswith("[x] English")
      and u.alt_liste.get(1).strip().startswith("[ ] Türkçe"), u.alt_liste.get(0))
dogru("imlec secili dilde", u.alt_secim == 0)
dogru("dil hala en", u.ayar["dil"] == "en")
tus(u, "<KeyPress-j>")                      # Türkçe
tus(u, "<KeyPress-Return>")
dogru("dil tr oldu", u.ayar["dil"] == "tr", u.ayar["dil"])
dogru("palet acik kaldi, listeye dondu", u.mod == "palet" and u.palet_kip == "liste"
      and not u.alt_menu.winfo_ismapped())
dogru("rubricrc'ye kalici yazildi", "set dil tr" in open(RC, encoding="utf-8").read())
dogru("ileti turkce", u.durum.cget("text") == "dil: Türkçe", u.durum.cget("text"))
dogru("secim dil satirinda kaldi", u.palet_secili() == "dil", str(u.palet_secili()))
u.palet_desen.set(""); u.update()
satirlar = u.palet_liste.get(0, "end")
dogru("turkce grup basligi", " [ yakınlaştırma ve düzen ]" in satirlar)
dogru("turkce aciklama (harfleriyle)", any("sığdır" in s for s in satirlar))
dogru("sol sutun turkce harfli", any(s.startswith("  aşağı ") for s in satirlar)
      and any(s.startswith("  sığdır-genişlik ") for s in satirlar)
      and any(s.startswith("  çık ") for s in satirlar))
dogru("palet istemi turkce", u.palet_alt_sol.cget("text") == "$ rubric --eylemler")
u.eylem_menusu(); u.update()
dogru("eylem basligi turkce ad", u.alt_baslik.cget("text") == "[ eylemler: aşağı ]",
      u.alt_baslik.cget("text"))
u.alt_menuyu_kapat()
u.palet_desen.set("asagi"); u.update()      # aksansiz ad da bulur
dogru("'asagi' -> 'aşağı'", u.palet_secili() == "asagi", str(u.palet_secili()))
u.palet_desen.set("next-page"); u.update()  # baska dildeki ad da bulur
dogru("'next-page' turkcede de bulundu", u.palet_secili() == "sonraki-sayfa",
      str(u.palet_secili()))
u.palet_desen.set("sigdir"); u.update()   # aksansiz yazan da bulsun
dogru("'sigdir' -> 'sığdır' bulundu", u.palet_secili() == "sigdir-genislik",
      str(u.palet_secili()))
tus(u, "<KeyPress-Escape>")
u.komutu_isle("lang de")
dogru(":lang de", u.ayar["dil"] == "de" and "set dil de" in open(RC, encoding="utf-8").read())
dogru("almanca ileti", u.durum.cget("text") == "Sprache: Deutsch", u.durum.cget("text"))
u.komutu_isle("lang xx")
dogru("bilinmeyen dil reddedildi", u.ayar["dil"] == "de", u.durum.cget("text"))
u.komutu_isle("set dil tr")
dogru(":set dil tr (kalici degil)", u.ayar["dil"] == "tr"
      and "set dil de" in open(RC, encoding="utf-8").read())
u.komutu_isle("set dil klingon")
dogru(":set gecersiz dil reddedildi", u.ayar["dil"] == "tr", u.durum.cget("text"))
u.komutu_isle("lang"); u.update()           # tek basina: secim listesi
dogru(":lang listeyi acti", u.mod == "palet" and u.palet_kip == "dil"
      and u.alt_secim == 1, f"{u.mod} {u.palet_kip} {u.alt_secim}")
# Esc isleyiciye dogrudan: odakta olmayan pencerede event_generate ara sira yutuluyor
u.palet_tus(_Olay("Escape")); u.update()
dogru("esc listeyi kapatti, dil degismedi", u.palet_kip == "liste" and u.ayar["dil"] == "tr")
u.palet_tus(_Olay("Escape")); u.update()
print("\n-- her dildeki komut adi --")
u.komutu_isle("next-page"); u.update()
dogru(":next-page calisti", u.durum.cget("text") != u.m("bilinmeyen_komut", ad="next-page"))
u.komutu_isle("aşağı")
dogru(":aşağı calisti", "aşağı" not in u.durum.cget("text"), u.durum.cget("text"))
u.tuslar["<F8>"] = "nächste-seite"          # rubricrc'de baska dilde yazilmis map
dogru("baska dilde map palete dogru komutta", "<F8>" in u.komut_tuslari().get("sonraki-sayfa", []))
del u.tuslar["<F8>"]
u.komutu_isle("lang en")
dogru("en'e dondu", u.ayar["dil"] == "en", u.ayar["dil"])
yeni = rubric.Yapilandirma()
yeni.yukle(RC)
dogru("rubricrc yeniden okununca dil en", yeni.ayar["dil"] == "en" and not yeni.hatalar,
      str(yeni.hatalar))

print("\n-- temalar --")
u.komutu_isle("lang tr"); u.update()
tus(u, "<Control-KeyPress-k>")
satirlar = u.palet_liste.get(0, "end")
dogru("temalar en altta, tek satir", satirlar[-2].strip() == "[ temalar ]"
      and u.palet_satirlar[-1] == "tema", str(satirlar[-2:]))
dogru("tema-<ad> satirlari palette yok",
      not any(k and k.startswith("tema-") for k in u.palet_satirlar))
u._palet_komuta_git("tema"); u.update()
u.palet_calistir(); u.update()                 # Enter: secim listesi
dogru("tema listesi acildi", u.palet_kip == "tema" and u.alt_ogeleri == list(rubric.TEMALAR),
      f"{u.palet_kip} {len(u.alt_ogeleri)}")
dogru("secili tema isaretli", u.alt_liste.get(0).strip().startswith("[x] kırmızı-fosfor"),
      u.alt_liste.get(0))
dogru("imlec secili temada", u.alt_secim == 0)
dogru("satir kendi renginde", u.alt_liste.itemcget(1, "foreground")
      == rubric.TEMALAR["yesil-fosfor"]["vurgu"], u.alt_liste.itemcget(1, "foreground"))
for _ in range(list(rubric.TEMALAR).index("neon")):
    u.palet_tus(_Olay("j", "j")); u.update()
u.palet_tus(_Olay("Return")); u.update()
dogru("neon uygulandi", u.ayar["tema"] == "neon" and u.ayar["zemin"] == rubric.TEMALAR["neon"]["zemin"])
dogru("palet acik, secim tema satirinda", u.mod == "palet" and u.palet_kip == "liste"
      and u.palet_secili() == "tema", f"{u.mod} {u.palet_kip} {u.palet_secili()}")
dogru("widget'lar yeniden renklendi", u.tuval.cget("bg") == rubric.TEMALAR["neon"]["zemin"]
      and u.palet.cget("bg") == rubric.TEMALAR["neon"]["palet-zemin"]
      and u.liste.cget("bg") == rubric.TEMALAR["neon"]["panel-zemin"])
dogru("rubricrc'ye 'set tema neon'", "set tema neon" in open(RC, encoding="utf-8").read())
dogru("ileti", u.durum.cget("text") == "tema: neon", u.durum.cget("text"))
u.palet_calistir(); u.update()                 # yeniden ac: [x] neonda, imlec neonda
dogru("[x] neona gecti", any(u.alt_liste.get(i).strip().startswith("[x] neon")
                             for i in range(u.alt_liste.size()))
      and u.alt_secim == list(rubric.TEMALAR).index("neon"))
u.palet_tus(_Olay("Escape")); u.update()
dogru("esc: liste kapandi, tema degismedi", u.palet_kip == "liste" and u.ayar["tema"] == "neon")
u.palet_tus(_Olay("Escape")); u.update()
u.komutu_isle("tema"); u.update()
dogru(":tema listeyi acti", u.mod == "palet" and u.palet_kip == "tema")
u.palet_tus(_Olay("Escape")); u.palet_tus(_Olay("Escape")); u.update()
u.komutu_isle("theme ice"); u.update()          # ingilizce ad da olur
dogru(":theme ice -> buz", u.ayar["tema"] == "buz", u.ayar["tema"])
u.komutu_isle("tema yok-boyle"); u.update()
dogru("bilinmeyen tema reddedildi", u.ayar["tema"] == "buz", u.durum.cget("text"))
yeni = rubric.Yapilandirma()
yeni.yukle(RC)
dogru("rubricrc yeniden okununca buz", yeni.ayar["tema"] == "buz"
      and yeni.ayar["vurgu"] == rubric.TEMALAR["buz"]["vurgu"] and not yeni.hatalar, str(yeni.hatalar))
u.komutu_isle("set vurgu #123456")               # elle renk temanin ustunde kalir
u.komutu_isle("tema toprak"); u.update()
dogru("elle renk temanin ustunde", u.ayar["vurgu"] == "#123456"
      and u.ayar["zemin"] == rubric.TEMALAR["toprak"]["zemin"], u.ayar["vurgu"])
u.yapi.elle_renkler.clear()
u.komutu_isle("tema kirmizi-fosfor"); u.komutu_isle("lang en"); u.update()
dogru("varsayilana dondu", u.ayar["vurgu"] == rubric.VARSAYILAN_AYAR["vurgu"])

print("\n-- komut satirindan --")
if u.mod == "palet":
    u.paleti_kapat()
u.komutu_isle("eylemler")
u.update()
dogru("':eylemler' paleti acti", u.mod == "palet")
u.paleti_kapat()

u.cik()
print("\nHATA SAYISI:", len(hata))
for h in hata:
    print("  !", h)
print("gecici rubricrc:", RC)
