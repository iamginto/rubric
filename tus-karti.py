# -*- coding: utf-8 -*-
"""
rubric tus haritasini PDF referans kartina dokur.

    uv run tus-karti.py [cikti.pdf] [--dil en|tr|de]

Tuslar elle yazilmaz: rubric.py icindeki VARSAYILAN_TUSLAR okunur ve komut ->
tus yonunde ters cevrilir. Aciklamalar ve grup sirasi da oradan gelir
(ACIKLAMALAR / KOMUT_GRUPLARI) - eylem paleti de ayni tabloyu kullaniyor,
iki yerde ayri ayri durmasinlar. Burada yalnizca kartin kendi bolumleri var.

Dil verilmezse rubricrc'deki `set dil` (yoksa en) kullanilir: kart uygulamayla
ayni dili konusur. Consolas Turkce ve Almanca harflerin hepsini tasiyor.
"""

from __future__ import annotations

import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rubric  # noqa: E402  (tus haritasi icin)


# --- gorunum: rubric'in kendi paleti ------------------------------------------
# Renkler burada tekrar yazilmaz, uygulamanin ayar tablosundan gelir; tema
# degisince kart da kendiliginden doner.

ZEMIN     = rubric.renk("zemin")
CUBUK     = rubric.renk("cubuk-zemin")
ON        = rubric.renk("cubuk-on")
VURGU     = rubric.renk("vurgu")
SONUK     = rubric.renk("sonuk")
UYARI     = rubric.renk("uyari")
CIZGI     = rubric.renk("sayfa-cerceve")

DUZ  = r"C:\Windows\Fonts\consola.ttf"
KALIN = r"C:\Windows\Fonts\consolab.ttf"

SAYFA_EN, SAYFA_BOY = 595.0, 842.0      # A4 dikey
KENAR      = 34.0
SUTUN_ARA  = 24.0
SUTUN_EN   = (SAYFA_EN - 2 * KENAR - SUTUN_ARA) / 2
TUS_EN     = 96.0                       # tus sutununun genisligi
SATIR_BOY  = 11.0                       # 12.2 / 11.6'da tr/en kart ikinci sayfaya tasiyordu (dil, belge listesi satirlari)
BOY        = 7.8                        # govde punto
UST        = 96.0                       # ilk satirin ustten uzakligi
ALT_SINIR  = SAYFA_BOY - 46.0


# --- komutlar: tanimlari rubric.py'de -----------------------------------------

GRUPLAR = rubric.KOMUT_GRUPLARI

# Kartin kendi metinleri, dil dil. Eksik olan Ingilizcesine duser (metin()).
KART: dict[str, dict] = {
    "en": {
        "baslik":     "key map",
        "alt_baslik": "zathura-style document reader  -  every key can be changed in rubricrc",
        "istem":      "$ rubric --keys",
        "konu":       "keyboard shortcut reference card",
        "g_sayi":     "count prefix",
        "g_fare":     "mouse",
        "g_komut":    "command line  ( : )",
        "g_palet":    "action palette  ( Ctrl-K )",
        "g_rc":       "rubricrc  -  configuration",
        "sayi": [
            ("5j",   "5 lines down - the count prefix works everywhere"),
            ("42G",  "go to page 42"),
            ("3J",   "3 pages forward"),
            ("4+",   "zoom in four steps"),
        ],
        "fare": [
            ("wheel",          "scroll"),
            ("Ctrl+wheel",     "zoom in / out"),
            ("drag",           "grab and move the page"),
            ("Shift+drag",     "highlight text (plain drag while the v pen is on)"),
            ("right click",    "delete a highlight  (u: undo)"),
            ("double click",   "open a heading in the panel"),
        ],
        "komut": [
            (":open <path>",         "open a document  (:o  :e)"),
            (":quit",                "quit  (:q)"),
            (":reload",              "reload  (:r)"),
            (":goto <n>",            "go to page n"),
            (":zoom <percent>",      "set the zoom as a percentage"),
            (":rotate",              "rotate"),
            (":set <name> <value>",  "change a setting while running"),
            (":map <key> <command>", "rebind a key"),
            (":unmap <key>",         "remove a key binding"),
            (":bmark <name>",        "drop a bookmark  (:bm)"),
            (":blist",               "list bookmarks"),
            (":bdelete <name>",      "delete a bookmark"),
            (":nohl",                "clear search highlighting"),
            (":toc",                 "table of contents"),
            (":info",                "title, author, page count"),
            (":export <file.png>",   "write this page as a PNG"),
            (":lang [en|tr|de]",     "interface language; alone: pick from a list"),
            (":rc",                  "show the rubricrc path"),
            (":actions",             "action palette  (<C-k>)"),
            (":help",                "short key summary"),
        ],
        "rc": [
            ("file",     "%APPDATA%\\rubric\\rubricrc"),
            ("example",  "copy rubricrc.ornek there"),
            ("setting",  "set sayfa-arasi 24"),
            ("key",      "map <C-n> next-page"),
            ("remove",   "unmap d"),
            ("command",  "map <F2> :goto 1"),
            ("language", "set dil en"),
            ("note",     "a broken line only drops itself"),
        ],
        "palet": [
            ("<C-k>",      "action palette: all commands + keys"),
            ("type",       "filter by name, description or key"),
            ("<C-k>",      "actions for the selected command (bottom right)"),
            ("bind key",   "press a combination, Enter confirms"),
            ("persistent", "saved to rubricrc automatically"),
            ("undo",       "remove key / reset to default"),
        ],
    },
    "tr": {
        "baslik":     "tuş haritası",
        "alt_baslik": "zathura tadında belge okuyucu  -  her tuş rubricrc ile değiştirilebilir",
        "istem":      "$ rubric --tuşlar",
        "konu":       "klavye kısayolları başvuru kartı",
        "g_sayi":     "sayı öneki",
        "g_fare":     "fare",
        "g_komut":    "komut satırı  ( : )",
        "g_palet":    "eylem paleti  ( Ctrl-K )",
        "g_rc":       "rubricrc  -  yapılandırma",
        "sayi": [
            ("5j",   "5 satır aşağı - sayı öneki her yerde"),
            ("42G",  "42. sayfaya git"),
            ("3J",   "3 sayfa ileri"),
            ("4+",   "dört kademe yakınlaştır"),
        ],
        "fare": [
            ("tekerlek",       "kaydır"),
            ("Ctrl+tekerlek",  "yakınlaştır / uzaklaştır"),
            ("sürükle",        "sayfayı tutup taşı"),
            ("Shift+sürükle",  "metni vurgula (v ile kalem açıkken düz sürükle)"),
            ("sağ tık",        "vurguyu sil  (u: geri al)"),
            ("çift tık",       "panelde başlığı aç"),
        ],
        "komut": [
            (":open <yol>",        "belge aç  (:o  :e)"),
            (":quit",              "çık  (:q)"),
            (":reload",            "yeniden yükle  (:r)"),
            (":goto <n>",          "n. sayfaya git"),
            (":zoom <yüzde>",      "yakınlaştırmayı yüzdeyle ayarla"),
            (":rotate",            "döndür"),
            (":set <ad> <değer>",  "ayarı çalışırken değiştir"),
            (":map <tuş> <komut>", "tuşu yeniden bağla"),
            (":unmap <tuş>",       "tuşun bağlantısını kaldır"),
            (":bmark <ad>",        "yer imi bırak  (:bm)"),
            (":blist",             "yer imlerini listele"),
            (":bdelete <ad>",      "yer imini sil"),
            (":nohl",              "arama vurgusunu kapat"),
            (":toc",               "içindekiler"),
            (":info",              "başlık, yazar, sayfa sayısı"),
            (":export <yol.png>",  "bu sayfayı PNG olarak yaz"),
            (":lang [en|tr|de]",   "arayüz dili; tek başına: listeden seç"),
            (":rc",                "rubricrc yolunu söyle"),
            (":eylemler",          "eylem paleti  (<C-k>)"),
            (":help",              "kısa tuş özeti"),
        ],
        "rc": [
            ("dosya",   "%APPDATA%\\rubric\\rubricrc"),
            ("örnek",   "rubricrc.ornek dosyasını oraya kopyala"),
            ("ayar",    "set sayfa-arasi 24"),
            ("tuş",     "map <C-n> sonraki-sayfa"),
            ("kaldır",  "unmap d"),
            ("komut",   "map <F2> :goto 1"),
            ("dil",     "set dil tr"),
            ("not",     "bozuk satır yalnızca kendini düşürür"),
        ],
        "palet": [
            ("<C-k>",      "eylem paleti: bütün komutlar ve tuşları"),
            ("yaz",        "süzmek için ad, açıklama ya da tuş yaz"),
            ("<C-k>",      "seçili komutun eylemleri (sağ altta)"),
            ("tuş ata",    "bir bileşkeye bas, Enter onayla"),
            ("kalıcı",     "atama rubricrc'ye kendiliğinden yazılır"),
            ("geri al",    "tuşu kaldır / varsayılana dön"),
        ],
    },
    "de": {
        "baslik":     "Tastenbelegung",
        "alt_baslik": "Dokumentbetrachter im zathura-Stil  -  jede Taste in rubricrc änderbar",
        "istem":      "$ rubric --tasten",
        "konu":       "Referenzkarte der Tastenkürzel",
        "g_sayi":     "Zählpräfix",
        "g_fare":     "Maus",
        "g_komut":    "Befehlszeile  ( : )",
        "g_palet":    "Aktionspalette  ( Strg-K )",
        "g_rc":       "rubricrc  -  Konfiguration",
        "sayi": [
            ("5j",   "5 Zeilen nach unten - Zählpräfix geht überall"),
            ("42G",  "zu Seite 42"),
            ("3J",   "3 Seiten vor"),
            ("4+",   "vier Stufen vergrößern"),
        ],
        "fare": [
            ("Mausrad",        "scrollen"),
            ("Strg+Mausrad",   "vergrößern / verkleinern"),
            ("Ziehen",         "Seite greifen und verschieben"),
            ("Shift+Ziehen",   "Text markieren (mit v-Stift einfach ziehen)"),
            ("Rechtsklick",    "Markierung löschen  (u: rückgängig)"),
            ("Doppelklick",    "Überschrift im Panel öffnen"),
        ],
        "komut": [
            (":open <Pfad>",          "Dokument öffnen  (:o  :e)"),
            (":quit",                 "beenden  (:q)"),
            (":reload",               "neu laden  (:r)"),
            (":goto <n>",             "zu Seite n"),
            (":zoom <Prozent>",       "Zoom in Prozent setzen"),
            (":rotate",               "drehen"),
            (":set <Name> <Wert>",    "Einstellung zur Laufzeit ändern"),
            (":map <Taste> <Befehl>", "Taste neu belegen"),
            (":unmap <Taste>",        "Tastenbelegung entfernen"),
            (":bmark <Name>",         "Lesezeichen setzen  (:bm)"),
            (":blist",                "Lesezeichen auflisten"),
            (":bdelete <Name>",       "Lesezeichen löschen"),
            (":nohl",                 "Suchhervorhebung ausschalten"),
            (":toc",                  "Inhaltsverzeichnis"),
            (":info",                 "Titel, Autor, Seitenzahl"),
            (":export <Datei.png>",   "diese Seite als PNG schreiben"),
            (":lang [en|tr|de]",      "Sprache; allein: aus Liste wählen"),
            (":rc",                   "Pfad der rubricrc anzeigen"),
            (":aktionen",             "Aktionspalette  (<C-k>)"),
            (":help",                 "kurze Tastenübersicht"),
        ],
        "rc": [
            ("Datei",       "%APPDATA%\\rubric\\rubricrc"),
            ("Beispiel",    "rubricrc.ornek dorthin kopieren"),
            ("Einstellung", "set sayfa-arasi 24"),
            ("Taste",       "map <C-n> nächste-seite"),
            ("entfernen",   "unmap d"),
            ("Befehl",      "map <F2> :goto 1"),
            ("Sprache",     "set dil de"),
            ("Hinweis",     "eine kaputte Zeile fällt nur selbst weg"),
        ],
        "palet": [
            ("<C-k>",          "Aktionspalette: alle Befehle und ihre Tasten"),
            ("tippen",         "Name, Beschreibung oder Taste filtert"),
            ("<C-k>",          "Aktionen des gewählten Befehls (unten rechts)"),
            ("Taste zuweisen", "Kombination drücken, Enter bestätigt"),
            ("dauerhaft",      "Belegung landet von selbst in rubricrc"),
            ("zurück",         "Taste entfernen / auf Standard zurück"),
        ],
    },
}


def metin(dil: str, anahtar: str):
    return KART.get(dil, {}).get(anahtar) or KART["en"][anahtar]


def kart_dili(argumanlar: list[str]) -> tuple[str, list[str]]:
    """`--dil xx` argumanini ayiklar; yoksa rubricrc'deki dil. Kalanlari da doner."""
    if "--dil" in argumanlar:
        i = argumanlar.index("--dil")
        dil = argumanlar[i + 1] if i + 1 < len(argumanlar) else ""
        kalan = argumanlar[:i] + argumanlar[i + 2:]
        if dil not in rubric.DILLER:
            sys.exit(f"bilinmeyen dil: {dil!r} (secenekler: {' '.join(rubric.DILLER)})")
        return dil, kalan
    yapi = rubric.Yapilandirma()
    yapi.yukle()
    return yapi.ayar["dil"], argumanlar


def tus_haritasi() -> dict[str, list[str]]:
    """komut -> o komuta bagli tuslar (rubric.py'den okunur)."""
    ters: dict[str, list[str]] = {}
    for tus, komut in rubric.VARSAYILAN_TUSLAR.items():
        ters.setdefault(komut, []).append(tus)
    return ters


class Kart:
    """Iki sutunlu, gerekince sayfa ekleyen basit bir akis dizici."""

    def __init__(self, yol: str, dil: str = "en"):
        self.belge = pymupdf.open()
        self.yol = yol
        self.dil = dil
        self.sayfa = None
        self.sayfa_no = 0
        self.sutun = 0
        self.y = 0.0
        # Metin genisligi tahmin edilmez, fontun kendisine olcturulur; sutun
        # tasmalarinin tek guvenilir caresi bu.
        self.font = pymupdf.Font(fontfile=DUZ)
        self.yeni_sayfa()

    def genislik(self, metin: str, boy: float = BOY) -> float:
        return self.font.text_length(metin, boy)

    def sar(self, metin: str, en: float) -> list[str]:
        """Metni verilen piksel genisligine kelime kelime boler."""
        kelimeler = metin.split()
        if not kelimeler:
            return [""]
        satirlar, simdiki = [], kelimeler[0]
        for k in kelimeler[1:]:
            aday = f"{simdiki} {k}"
            if self.genislik(aday) <= en:
                simdiki = aday
            else:
                satirlar.append(simdiki)
                simdiki = k
        satirlar.append(simdiki)
        return satirlar

    # -- alt yapi ----------------------------------------------------------

    def yeni_sayfa(self) -> None:
        self.sayfa = self.belge.new_page(width=SAYFA_EN, height=SAYFA_BOY)
        self.sayfa_no += 1
        self.sayfa.draw_rect(self.sayfa.rect, color=None, fill=ZEMIN)
        self.sayfa.insert_font(fontname="cons", fontfile=DUZ)
        self.sayfa.insert_font(fontname="consb", fontfile=KALIN)
        self.baslik()
        self.alt_cubuk()
        self.sutun = 0
        self.y = UST

    def yaz(self, x: float, y: float, metin: str, renk=ON,
            boy: float = BOY, kalin: bool = False) -> None:
        self.sayfa.insert_text((x, y), metin, fontsize=boy,
                               fontname="consb" if kalin else "cons",
                               color=renk)

    def baslik(self) -> None:
        if self.sayfa_no == 1:
            self.yaz(KENAR, 56, "rubric", VURGU, 26, kalin=True)
            self.yaz(KENAR + 76, 56, metin(self.dil, "baslik"), SONUK, 11)
            self.yaz(KENAR, 71, metin(self.dil, "alt_baslik"), SONUK, 7.6)
        else:
            self.yaz(KENAR, 56, "rubric", VURGU, 15, kalin=True)
            self.yaz(KENAR + 44, 56, metin(self.dil, "baslik"), SONUK, 8)
        self.sayfa.draw_line(pymupdf.Point(KENAR, 80),
                             pymupdf.Point(SAYFA_EN - KENAR, 80),
                             color=CIZGI, width=0.8)

    def alt_cubuk(self) -> None:
        """Uygulamanin durum cubugunun ayni: solda ad, sagda sayfa.

        Sayfa numarasi burada yazilmaz: toplam sayfa sayisi ancak dizim
        bitince belli olur, o yuzden kaydet() sirasinda islenir.
        """
        y = SAYFA_BOY - 34
        self.sayfa.draw_rect(pymupdf.Rect(0, y, SAYFA_EN, SAYFA_BOY),
                             color=None, fill=CUBUK)
        self.yaz(KENAR, y + 14, metin(self.dil, "istem"), ON, 8)

    def sayfa_numaralari(self) -> None:
        toplam = self.belge.page_count
        for i, sayfa in enumerate(self.belge, 1):
            metin = f"{i}/{toplam}"
            sayfa.insert_text(
                (SAYFA_EN - KENAR - self.genislik(metin, 8), SAYFA_BOY - 20),
                metin, fontsize=8, fontname="cons", color=VURGU)

    # -- yerlesim ----------------------------------------------------------

    def sutun_x(self) -> float:
        return KENAR + self.sutun * (SUTUN_EN + SUTUN_ARA)

    def yer_ac(self, gereken: float) -> None:
        """Satir sigmiyorsa once oteki sutuna, o da dolduysa yeni sayfaya."""
        if self.y + gereken <= ALT_SINIR:
            return
        if self.sutun == 0:
            self.sutun = 1
            self.y = UST
        else:
            self.yeni_sayfa()

    def grup_basligi(self, ad: str) -> None:
        self.yer_ac(SATIR_BOY * 3)
        x = self.sutun_x()
        self.yaz(x, self.y, f"[ {ad} ]", VURGU, 8.6, kalin=True)
        cizgi_x = x + self.genislik(f"[ {ad} ]", 8.6) + 6   # kalin biraz daha genis
        if cizgi_x < x + SUTUN_EN:
            self.sayfa.draw_line(pymupdf.Point(cizgi_x, self.y - 3),
                                 pymupdf.Point(x + SUTUN_EN, self.y - 3),
                                 color=CIZGI, width=0.7)
        self.y += SATIR_BOY * 1.25

    def satir(self, tus: str, aciklama: str, tus_rengi=VURGU) -> None:
        aciklama_en = SUTUN_EN - TUS_EN
        parcalar = self.sar(aciklama, aciklama_en)

        # Tus listesi kendi sutununa sigmiyorsa aciklama alt satirdan baslar.
        kaydir = self.genislik(tus) > TUS_EN - 6
        self.yer_ac(SATIR_BOY * (len(parcalar) + (1 if kaydir else 0)))

        x = self.sutun_x()
        self.yaz(x, self.y, tus, tus_rengi)
        if kaydir:
            self.y += SATIR_BOY
            x = self.sutun_x()

        for i, p in enumerate(parcalar):
            self.yaz(x + TUS_EN, self.y, p, ON)
            self.y += SATIR_BOY
            if i == 0:
                x = self.sutun_x()

    def bosluk(self, kat: float = 0.7) -> None:
        self.y += SATIR_BOY * kat

    def kaydet(self) -> None:
        self.sayfa_numaralari()
        self.belge.set_metadata({
            "title": f"rubric - {metin(self.dil, 'baslik')}",
            "author": "rubric",
            "subject": metin(self.dil, "konu"),
        })
        self.belge.save(self.yol, deflate=True, garbage=3)
        self.belge.close()


def uret(cikti: str, dil: str = "en") -> str:
    harita = tus_haritasi()
    k = Kart(cikti, dil)

    for grup, komutlar in GRUPLAR:
        if not any(harita.get(komut) for komut in komutlar):
            continue                    # tusu olmayan grup (temalar) kartta yer tutmasin
        k.grup_basligi(rubric.grup_adi(grup, dil))
        for komut in komutlar:
            tuslar = harita.get(komut, [])
            if not tuslar:
                continue
            k.satir("  ".join(tuslar), rubric.aciklama(komut, dil) or komut)
        k.bosluk()

    for baslik, bolum, renk in (("g_sayi", "sayi", VURGU), ("g_fare", "fare", UYARI),
                                ("g_komut", "komut", VURGU), ("g_palet", "palet", VURGU),
                                ("g_rc", "rc", UYARI)):
        k.grup_basligi(metin(dil, baslik))
        for tus, aciklama in metin(dil, bolum):
            k.satir(tus, aciklama, renk)
        if bolum != "rc":
            k.bosluk()

    k.kaydet()
    return cikti


if __name__ == "__main__":
    varsayilan = os.path.join(rubric.masaustu_yolu(), "rubric-tuslari.pdf")
    dil, kalan = kart_dili(sys.argv[1:])
    hedef = kalan[0] if kalan else varsayilan
    print(f"yazildi ({dil}):", uret(hedef, dil))
