# -*- coding: utf-8 -*-
"""rubricrc okuyucusu: satir sonu yorumlari, renkler, ornek dosyanin tamami."""
import os
import sys
import tempfile

import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric

hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


print("-- satir sonu yorumu --")
for girdi, beklenen in [
    ("true  # gece modu", "true"),
    ("true\t# sekmeyle", "true"),
    ("#0c0909", "#0c0909"),
    ("#0c0909   # zemin", "#0c0909"),
    ("genislik # genislik | sayfa | yok", "genislik"),
    ("{ad} [{sayfa}/{toplam}] - rubric", "{ad} [{sayfa}/{toplam}] - rubric"),
    ("a#b", "a#b"),
]:
    cikan = rubric._yorumsuz(girdi)
    dogru(f"{girdi!r} -> {cikan!r}", cikan == beklenen)

print("\n-- dosyadan --")
yol = os.path.join(tempfile.mkdtemp(prefix="rubric-rc-"), "rubricrc")
with open(yol, "w", encoding="utf-8") as f:
    f.write("set ters-renk true   # gece modu ile acilsin\n"
            "set zemin #101010  # koyu\n"
            "set onbellek 20 # sayfa\n"
            "set vurgu-rengi #66ff66\n")
y = rubric.Yapilandirma()
y.yukle(yol)
dogru("ters-renk true (eskiden yorum yuzunden false okunuyordu)", y.ayar["ters-renk"] is True)
dogru("zemin rengi temiz", y.ayar["zemin"] == "#101010", repr(y.ayar["zemin"]))
dogru("sayi yorumlu da okunur", y.ayar["onbellek"] == 20)
dogru("vurgu-rengi", y.ayar["vurgu-rengi"] == "#66ff66")
dogru("hata yok", not y.hatalar, str(y.hatalar))

print("\n-- depodaki rubricrc.ornek --")
y = rubric.Yapilandirma()
y.yukle(os.path.join(ortak.KOK, "rubricrc.ornek"))
dogru("ornek hatasiz okunuyor", not y.hatalar, str(y.hatalar[:3]))
farkli = {k: (v, y.ayar[k]) for k, v in rubric.VARSAYILAN_AYAR.items() if y.ayar[k] != v}
dogru("ornekteki degerler varsayilanlarla ayni", not farkli, str(farkli))
dogru("ornekteki her tus/komut taninir",
      all(k in rubric.KOMUT_ACIKLAMA or k.startswith(":") for k in y.tuslar.values()),
      str([k for k in y.tuslar.values() if k not in rubric.KOMUT_ACIKLAMA][:5]))

print("\n-- tema --")
dogru("kirmizi-fosfor = varsayilan renkler",
      all(rubric.TEMALAR["kirmizi-fosfor"][a] == rubric.VARSAYILAN_AYAR[a] for a in rubric.RENK_ANAHTARLARI))
dogru("her tema butun renkleri veriyor",
      all(set(t) == set(rubric.RENK_ANAHTARLARI) for t in rubric.TEMALAR.values()))
yol2 = os.path.join(os.path.dirname(yol), "rubricrc-tema")
with open(yol2, "w", encoding="utf-8") as f:     # elle renk ONCE, tema SONRA yazilmis
    f.write("set vurgu #abcdef\nset tema kehribar\n")
y = rubric.Yapilandirma()
y.yukle(yol2)
dogru("tema sonra gelse de elle renk kalir", y.ayar["vurgu"] == "#abcdef"
      and y.ayar["zemin"] == rubric.TEMALAR["kehribar"]["zemin"], y.ayar["vurgu"])
y = rubric.Yapilandirma()
y.ata("tema", "Bernstein")                      # almanca ad, buyuk harf
dogru("tema adi her dilde", y.ayar["tema"] == "kehribar", y.ayar["tema"])

print("\n-- komut adlari (her dil) --")
kimlikler = set(rubric.KOMUT_ACIKLAMA)
for dil, adlar in rubric.KOMUT_ADLARI.items():
    dogru(f"{dil}: her komutun adi var", set(adlar) == kimlikler,
          str(kimlikler ^ set(adlar)))
    dogru(f"{dil}: adlar bosluksuz", all(" " not in a for a in adlar.values()))
cakisan = {}
for adlar in rubric.KOMUT_ADLARI.values():
    for kimlik, ad in adlar.items():
        cakisan.setdefault(rubric.katla(ad), set()).add(kimlik)
for kimlik in kimlikler:                     # ic kimlik de bir ad sayilir
    cakisan.setdefault(rubric.katla(kimlik), set()).add(kimlik)
cift = {a: k for a, k in cakisan.items() if len(k) > 1}
dogru("hicbir ad iki komutu gostermiyor", not cift, str(cift))
dogru("aşağı -> asagi", rubric.komut_kimligi("aşağı") == "asagi")
dogru("Nächste-Seite -> sonraki-sayfa", rubric.komut_kimligi("Nächste-Seite") == "sonraki-sayfa")

print("\nHATA SAYISI:", len(hata))
