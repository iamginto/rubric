# -*- coding: utf-8 -*-
"""
rubric - zathura tadinda, vim tuslu bir PDF okuyucu.

    uv run rubric.py <dosya.pdf>

Zathura'nin ana fikri burada da ayni: uygulama cikplak bir goruntuleyici,
davranisi yapilandirma dosyasi belirler. Her tus ve her ayar `rubricrc`
icinden ezilebilir; ic komutlar isimleriyle disariya acik.
"""

from __future__ import annotations

import collections
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog
from tkinter import font as tkfont

import pymupdf


# ---------------------------------------------------------------------------
# Varsayilanlar
# ---------------------------------------------------------------------------

VARSAYILAN_AYAR = {
    # --- renkler (koyu, kirmizi fosfor) ---
    # Tema tek: hep koyu, tek hue. Tus karti ve ikon da bu tabloyu okur
    # (bkz. renk()), yani rengi burada degistirmek hepsini birden dondurur.
    "zemin":          "#0c0909",   # tuval zemini
    "sayfa-cerceve":  "#2a1e20",   # sayfa kenar cizgisi
    "cubuk-zemin":    "#171011",   # durum cubugu zemini
    "cubuk-on":       "#d1908c",   # govde yazisi: sonuk kirmizi fosfor
    "vurgu":          "#ff5f57",   # fosforlu vurgu
    "uyari":          "#e3b341",
    "hata":           "#ff1e1e",   # vurgudan daha cig: hata bagirmali
    "arama-zemin":    "#e3b341",   # bulunan esleme
    "arama-aktif":    "#ff5f57",   # uzerinde durulan esleme
    "panel-zemin":    "#100b0c",   # icindekiler paneli
    "panel-secili":   "#2e1b1d",
    "sonuk":          "#6b4b4d",   # ikincil yazi: grup basligi, ipucu
    "palet-zemin":    "#150f10",   # eylem paleti (<C-k>)
    "palet-cerceve":  "#35262a",
    "vurgu-rengi":    "#ffd54a",   # metin vurgusu (fosforlu kalem; sayfa beyaz oldugu icin acik)
    # Yukaridaki renkler "kirmizi-fosfor" temasinin kendisi. `set tema <ad>`
    # (ya da Ctrl-K > temalar) hepsini birden degistirir; rubricrc'de elle
    # yazilan tek tek renkler, sira fark etmeksizin temanin USTUNE biner.
    "tema":           "kirmizi-fosfor",

    # --- yazitipi ---
    # Turkce (ş ğ ı İ) ve Almanca (ä ö ü ß) harflerinin hepsi olmali; yoksa
    # YEDEK_YAZITIPLERI'nden ilk bulunana dusulur (bkz. yazitipi_sec()).
    "yazitipi":       "Consolas",
    "yazitipi-boy":   10,

    # --- arayuz dili: en | tr | de (bkz. DILLER) ---
    "dil":            "en",

    # --- duzen ---
    "kenar-bosluk":   14,          # tuval kenari ile sayfa arasi
    "sayfa-arasi":    10,          # sayfalar arasi bosluk
    "sutunlar":       1,           # yan yana sayfa sayisi

    # --- davranis ---
    "kaydirma-adimi":      60,     # j/k ile kayan piksel
    "yatay-adim":          40,
    "yakinlastirma-adimi": 1.15,
    "en-az-yakinlastirma": 0.10,
    "en-cok-yakinlastirma": 10.0,
    "ters-renk":      False,       # gece modu (renkleri ters cevir)
    "son-konum":      True,        # dosyayi kaldigi yerden ac
    # Belge listesi (<C-Left>/<C-Right>). zathura'nin yolu: bellekte yalnizca
    # bakilan belge acik, digerleri yol + kaldigi yer; liste de sinirli
    # (zathura'da show-recent, varsayilani 10). Oturum zathura'da yok.
    "oturum":         True,        # kapatinca acik belgeleri hatirla, acilista geri getir
    "son-belgeler":   10,          # listede en cok kac belge; dolunca en uzun suredir bakilmayan cikar
    # q ile kapatilani <C-e> kaldigi yerden geri acar. 3: art arda iki kaza
    # + bir pay. Kullanici 1..KAPANAN_EN_COK arasinda secer (Ctrl-K > ayarlar).
    "kapanan-belgeler": 3,         # kac kapanan belge geri acilabilir
    "onbellek":       12,          # bellekte tutulan islenmis sayfa sayisi
    "sigdir":         "genislik",  # acilis sigdirma: genislik | sayfa | yok
    "durum-cubugu":   True,
    "baslik-cubugu":  True,        # rubric'in kendi (temali) ust bari
    "windows-basligi": False,      # Windows'un beyaz baslik cubugu

    # --- bicimler ---
    # Yer tutucular: {mod} {dosya} {ad} {yol} {sayfa} {toplam} {yuzde}
    #                {zoom} {sigdir} {sutun} {ters} {donme} {arama}
    #                {belgeler}  (" [2/3]": listede kacinci belge; tek belgede bos)
    "durum-bicimi":   "{mod} {ad}{belgeler}  {sayfa}/{toplam} ({yuzde}%)  z:{zoom}%  "
                      "{sigdir}{ters}{arama}",
    "baslik-bicimi":  "{ad} [{sayfa}/{toplam}] - rubric",
}

# `kapanan-belgeler`in ust siniri: rubricrc'ye 50 yazilsa da 10'a iner.
KAPANAN_EN_COK = 10

# Palette [x] secim listesi acan komutlarin alt menu kipleri
SECIM_KIPLERI = ("dil", "tema", "sinir")

# tus -> ic komut adi
VARSAYILAN_TUSLAR = {
    "j": "asagi",           "<Down>": "asagi",
    "k": "yukari",          "<Up>": "yukari",
    "h": "sola",            "<Left>": "sola",
    "l": "saga",            "<Right>": "saga",
    "<C-d>": "yarim-asagi", "<C-u>": "yarim-yukari",
    "<C-f>": "sayfa-ileri", "<Space>": "sayfa-ileri", "<Next>": "sayfa-ileri",
    "<C-b>": "sayfa-geri",  "<Prior>": "sayfa-geri",
    "J": "sonraki-sayfa",   "K": "onceki-sayfa",
    "gg": "ilk-sayfa",      "G": "son-sayfa",
    "<Home>": "ilk-sayfa",  "<End>": "son-sayfa",

    "+": "yakinlastir",     "=": "yakinlastir",     "-": "uzaklastir",
    "s": "sigdir-genislik", "a": "sigdir-sayfa",    "<C-0>": "yakinlastirma-sifirla",

    "r": "dondur",          "<C-r>": "ters-renk",   "d": "cift-sayfa",
    "<Tab>": "icindekiler", "<F11>": "tam-ekran",   "<F5>": "sunum",
    "<C-m>": "durum-cubugu", "<C-k>": "eylemler",

    "/": "ara-ileri",       "?": "ara-geri",
    "n": "sonraki-bulgu",   "N": "onceki-bulgu",
    "<Esc>": "vurguyu-kapat",

    # q yalnizca bakilan belgeyi kapatir (sonuncusu kapaninca bos ekran);
    # uygulamadan cikmak Q. Kaza ile her seyi kapatmak zorlassin diye.
    ":": "komut-modu",      "q": "belgeyi-kapat",   "Q": "cik",
    "m": "isaret-koy",      "'": "isarete-git",
    "<C-o>": "geri-zipla",  "<C-i>": "ileri-zipla",
    "R": "yeniden-yukle",   "o": "ac",
    "<C-Right>": "sonraki-belge", "<C-Left>": "onceki-belge",
    "<C-w>": "belgeyi-kapat",     "B": "belgeler",
    # Ctrl+Shift+T degil: birden cok klavye dili kuruluyken Windows Ctrl+Shift'i
    # dil degistirmeye ayirabiliyor. <C-e> vim'deki satir kaydirma ama rubric'te bos.
    "<C-e>": "kapanani-ac",
    "v":"vurgu-kalemi",    "V": "vurgular",        "u": "vurgu-geri-al",
}

OZEL_TUSLAR = {
    "Return": "<Return>", "KP_Enter": "<Return>", "Escape": "<Esc>",
    "space": "<Space>", "Tab": "<Tab>", "ISO_Left_Tab": "<S-Tab>",
    "BackSpace": "<BackSpace>", "Delete": "<Delete>",
    "Up": "<Up>", "Down": "<Down>", "Left": "<Left>", "Right": "<Right>",
    "Prior": "<Prior>", "Next": "<Next>", "Home": "<Home>", "End": "<End>",
}
for _i in range(1, 13):
    OZEL_TUSLAR[f"F{_i}"] = f"<F{_i}>"

# ---------------------------------------------------------------------------
# Diller
#
# Ic komut ve ayar adlari (asagi, sigdir-sayfa, set ters-renk ...) dile gore
# DEGISMEZ: rubricrc'de yaziliyorlar, cevrilirse kullanicinin dosyasi bozulur.
# Cevrilen yalnizca ekranda okunan metin. Eksik bir cevirinin yerine
# Ingilizcesi gelir; dil eklemek = DILLER'e ad, asagidaki tablolara bir sutun.
# ---------------------------------------------------------------------------

DILLER = {"en": "English", "tr": "Türkçe", "de": "Deutsch"}

# Her ic komutun ne ise yaradigi. Tek yerde durur: eylem paleti de, masaustune
# uretilen tus karti da (tus-karti.py) buradan okur.
ACIKLAMALAR: dict[str, dict[str, str]] = {
    "en": {
        "asagi":          "scroll down line by line",
        "yukari":         "scroll up line by line",
        "sola":           "scroll left (when zoomed in)",
        "saga":           "scroll right",
        "yarim-asagi":    "half a screen down",
        "yarim-yukari":   "half a screen up",
        "sayfa-ileri":    "one screen forward",
        "sayfa-geri":     "one screen back",
        "sonraki-sayfa":  "jump to the top of the next page",
        "onceki-sayfa":   "jump to the top of the previous page",
        "ilk-sayfa":      "start of the document",
        "son-sayfa":      "end of the document - 42G / 42 enter goes to page 42",

        "yakinlastir":    "zoom in",
        "uzaklastir":     "zoom out",
        "sigdir-genislik": "fit the page to the window width",
        "sigdir-sayfa":   "fit the whole page on screen",
        "yakinlastirma-sifirla": "actual size (100%)",
        "dondur":         "rotate 90 degrees",
        "cift-sayfa":     "toggle single / double page layout",
        "ters-renk":      "night mode: invert colors",

        "icindekiler":    "table of contents - j k Enter Esc",
        "eylemler":       "action palette: commands and key bindings",
        "tam-ekran":      "full screen",
        "sunum":          "presentation: full screen + fit page",
        "durum-cubugu":   "hide / show the status bar",
        "baslik-cubugu":  "hide / show the top bar (persistent)",
        "dil":            "interface language: English / Türkçe / Deutsch (persistent)",

        "ara-ileri":      "search forward",
        "ara-geri":       "search backward",
        "sonraki-bulgu":  "next match",
        "onceki-bulgu":   "previous match",
        "vurguyu-kapat":  "end the search, clear match marks; put the pen down",

        "isaret-koy":     "set a mark - then press a letter",
        "isarete-git":    "go back to a mark - then the same letter",
        "geri-zipla":     "back in the jump history",
        "ileri-zipla":    "forward in the jump history",

        "vurgu-kalemi":   "highlighter pen: dragging highlights text (Shift+drag always does)",
        "vurgular":       "highlight list - Enter go, x delete",
        "vurgu-geri-al":  "undo the last highlight add / delete",
        "vurgulari-aktar": "write a highlighted copy (<name>-highlighted.pdf, original untouched)",

        "ac":             "pick a file and open it",
        "yeniden-yukle":  "reload the document from disk",
        "komut-modu":     "open the command line",
        "cik":            "quit rubric (documents and positions are saved)",
        "sonraki-belge":  "next document in the list (newer)",
        "onceki-belge":   "previous document in the list (older)",
        "belgeyi-kapat":  "close this document, go to its neighbour (Q quits)",
        "kapanani-ac":    "reopen the last closed document where it was, same spot in the list",
        "geri-acma-siniri": "how many closed documents can be reopened: 1-10 (persistent)",
        "belgeler":       "open documents - Enter go, x close",
    },
    "tr": {
        "asagi":          "satır satır aşağı kaydır",
        "yukari":         "satır satır yukarı kaydır",
        "sola":           "sola kaydır (yakınlaştırınca)",
        "saga":           "sağa kaydır",
        "yarim-asagi":    "yarım ekran aşağı",
        "yarim-yukari":   "yarım ekran yukarı",
        "sayfa-ileri":    "bir ekran ileri",
        "sayfa-geri":     "bir ekran geri",
        "sonraki-sayfa":  "sonraki sayfanın başına atla",
        "onceki-sayfa":   "önceki sayfanın başına atla",
        "ilk-sayfa":      "belgenin başı",
        "son-sayfa":      "belgenin sonu - 42G / 42 enter ise 42. sayfa",

        "yakinlastir":    "yakınlaştır",
        "uzaklastir":     "uzaklaştır",
        "sigdir-genislik": "sayfayı pencere genişliğine sığdır",
        "sigdir-sayfa":   "sayfanın tamamı ekrana sığsın",
        "yakinlastirma-sifirla": "gerçek boyut (%100)",
        "dondur":         "90 derece döndür",
        "cift-sayfa":     "tek / çift sayfa düzeni arasında geçiş",
        "ters-renk":      "gece modu: renkleri ters çevir",

        "icindekiler":    "içindekiler paneli - j k Enter Esc",
        "eylemler":       "eylem paleti: komutlar ve tuş atama",
        "tam-ekran":      "tam ekran",
        "sunum":          "sunum: tam ekran + sayfaya sığdır",
        "durum-cubugu":   "durum çubuğunu gizle / göster",
        "baslik-cubugu":  "üst barı gizle / göster (kalıcı)",
        "dil":            "arayüz dili: English / Türkçe / Deutsch (kalıcı)",

        "ara-ileri":      "ileri doğru ara",
        "ara-geri":       "geri doğru ara",
        "sonraki-bulgu":  "sonraki eşleşme",
        "onceki-bulgu":   "önceki eşleşme",
        "vurguyu-kapat":  "aramayı bitir, eşleşme işaretlerini sil; kalemi bırak",

        "isaret-koy":     "işaret koy - sonra bir harfe bas",
        "isarete-git":    "işarete dön - sonra aynı harf",
        "geri-zipla":     "zıplama geçmişinde geri",
        "ileri-zipla":    "zıplama geçmişinde ileri",

        "vurgu-kalemi":   "vurgu kalemi: sürükleyince metni vurgular (Shift+sürükle her zaman)",
        "vurgular":       "vurgu listesi - Enter git, x sil",
        "vurgu-geri-al":  "son vurgu ekleme / silmesini geri al",
        "vurgulari-aktar": "vurgulu kopya PDF yaz (<ad>-vurgulu.pdf, aslı değişmez)",

        "ac":             "dosya seçip aç",
        "yeniden-yukle":  "belgeyi diskten yeniden oku",
        "komut-modu":     "komut satırını aç",
        "cik":            "rubric'ten çık (belgeler ve konumlar kaydedilir)",
        "sonraki-belge":  "listedeki sonraki belge (daha yeni)",
        "onceki-belge":   "listedeki önceki belge (daha eski)",
        "belgeyi-kapat":  "bu belgeyi kapat, komşusuna geç (Q çıkar)",
        "kapanani-ac":    "son kapatılan belgeyi kaldığı yerden, listedeki yerine geri aç",
        "geri-acma-siniri": "kapatılan kaç belge geri açılabilsin: 1-10 (kalıcı)",
        "belgeler":       "açık belgeler - Enter git, x kapat",
    },
    "de": {
        "asagi":          "zeilenweise nach unten scrollen",
        "yukari":         "zeilenweise nach oben scrollen",
        "sola":           "nach links scrollen (bei Vergrößerung)",
        "saga":           "nach rechts scrollen",
        "yarim-asagi":    "halben Bildschirm nach unten",
        "yarim-yukari":   "halben Bildschirm nach oben",
        "sayfa-ileri":    "einen Bildschirm vor",
        "sayfa-geri":     "einen Bildschirm zurück",
        "sonraki-sayfa":  "zum Anfang der nächsten Seite",
        "onceki-sayfa":   "zum Anfang der vorigen Seite",
        "ilk-sayfa":      "Anfang des Dokuments",
        "son-sayfa":      "Ende des Dokuments - 42G / 42 Enter: Seite 42",

        "yakinlastir":    "vergrößern",
        "uzaklastir":     "verkleinern",
        "sigdir-genislik": "Seite an die Fensterbreite anpassen",
        "sigdir-sayfa":   "ganze Seite auf den Bildschirm einpassen",
        "yakinlastirma-sifirla": "Originalgröße (100%)",
        "dondur":         "um 90 Grad drehen",
        "cift-sayfa":     "zwischen Einzel- und Doppelseite wechseln",
        "ters-renk":      "Nachtmodus: Farben invertieren",

        "icindekiler":    "Inhaltsverzeichnis - j k Enter Esc",
        "eylemler":       "Aktionspalette: Befehle und Tastenbelegung",
        "tam-ekran":      "Vollbild",
        "sunum":          "Präsentation: Vollbild + Seite einpassen",
        "durum-cubugu":   "Statusleiste aus- / einblenden",
        "baslik-cubugu":  "Titelleiste aus- / einblenden (dauerhaft)",
        "dil":            "Oberflächensprache: English / Türkçe / Deutsch (dauerhaft)",

        "ara-ileri":      "vorwärts suchen",
        "ara-geri":       "rückwärts suchen",
        "sonraki-bulgu":  "nächster Treffer",
        "onceki-bulgu":   "vorheriger Treffer",
        "vurguyu-kapat":  "Suche beenden, Treffer löschen; Stift weglegen",

        "isaret-koy":     "Marke setzen - dann einen Buchstaben drücken",
        "isarete-git":    "zur Marke zurück - dann derselbe Buchstabe",
        "geri-zipla":     "im Sprungverlauf zurück",
        "ileri-zipla":    "im Sprungverlauf vor",

        "vurgu-kalemi":   "Textmarker: Ziehen markiert Text (Shift+Ziehen immer)",
        "vurgular":       "Markierungsliste - Enter springen, x löschen",
        "vurgu-geri-al":  "letztes Markieren / Löschen rückgängig machen",
        "vurgulari-aktar": "markierte Kopie schreiben (<Name>-markiert.pdf, Original bleibt)",

        "ac":             "Datei auswählen und öffnen",
        "yeniden-yukle":  "Dokument neu von der Festplatte laden",
        "komut-modu":     "Befehlszeile öffnen",
        "cik":            "rubric beenden (Dokumente und Positionen bleiben)",
        "sonraki-belge":  "nächstes Dokument der Liste (neuer)",
        "onceki-belge":   "voriges Dokument der Liste (älter)",
        "belgeyi-kapat":  "dieses Dokument schließen, zum Nachbarn (Q beendet)",
        "kapanani-ac":    "zuletzt geschlossenes Dokument an alter Stelle wieder öffnen",
        "geri-acma-siniri": "wie viele geschlossene Dokumente wieder öffnen: 1-10 (dauerhaft)",
        "belgeler":       "offene Dokumente - Enter öffnen, x schließen",
    },
}
# Hangi adlarin ic komut oldugunu soyleyen tablo (testler ve eski betikler
# bu adla ariyor); metinleri icin aciklama() kullan.
KOMUT_ACIKLAMA = ACIKLAMALAR["en"]

# Komutlarin sunulus sirasi; hem palet hem tus karti ayni bolumleri kullanir.
# Ilk eleman grubun kimligi, ekrandaki adi GRUP_ADLARI'ndan gelir.
KOMUT_GRUPLARI = [
    ("gezinme", [
        "asagi", "yukari", "sola", "saga",
        "yarim-asagi", "yarim-yukari", "sayfa-ileri", "sayfa-geri",
        "sonraki-sayfa", "onceki-sayfa", "ilk-sayfa", "son-sayfa",
    ]),
    ("yakinlastirma ve duzen", [
        "yakinlastir", "uzaklastir", "sigdir-genislik", "sigdir-sayfa",
        "yakinlastirma-sifirla", "dondur", "cift-sayfa", "ters-renk",
    ]),
    ("ekran", ["icindekiler", "eylemler", "tam-ekran", "sunum", "durum-cubugu",
               "baslik-cubugu", "dil"]),
    ("arama", ["ara-ileri", "ara-geri", "sonraki-bulgu", "onceki-bulgu",
               "vurguyu-kapat"]),
    ("isaret ve ziplama", ["isaret-koy", "isarete-git", "geri-zipla",
                           "ileri-zipla"]),
    ("vurgu", ["vurgu-kalemi", "vurgular", "vurgu-geri-al", "vurgulari-aktar"]),
    ("dosya", ["ac", "belgeler", "sonraki-belge", "onceki-belge", "belgeyi-kapat",
               "kapanani-ac", "yeniden-yukle", "komut-modu", "cik"]),
    ("ayarlar", ["geri-acma-siniri"]),
]

GRUP_ADLARI: dict[str, dict[str, str]] = {
    "en": {"gezinme": "navigation", "yakinlastirma ve duzen": "zoom and layout",
           "ekran": "display", "arama": "search", "isaret ve ziplama": "marks and jumps",
           "vurgu": "highlights", "dosya": "file", "ayarlar": "settings"},
    "tr": {"gezinme": "gezinme", "yakinlastirma ve duzen": "yakınlaştırma ve düzen",
           "ekran": "ekran", "arama": "arama", "isaret ve ziplama": "işaret ve zıplama",
           "vurgu": "vurgu", "dosya": "dosya", "ayarlar": "ayarlar"},
    "de": {"gezinme": "Navigation", "yakinlastirma ve duzen": "Zoom und Layout",
           "ekran": "Anzeige", "arama": "Suche", "isaret ve ziplama": "Marken und Sprünge",
           "vurgu": "Markierungen", "dosya": "Datei", "ayarlar": "Einstellungen"},
}

# Arayuzun geri kalan metni. Ikili deger (tekil, cogul): hangisi oldugunu
# `n` belirler; Turkcede sayidan sonra ad tekil kaldigi icin tek dize yeter.
# Dilden bagimsiz kaliplar (ornegin "rubricrc:{no}: {e}") yalnizca "en"de durur.
METINLER: dict[str, dict[str, str | tuple[str, str]]] = {
    "en": {
        "ipucu_bos":        "o: open file   <C-k>: actions   :open <path>   :help   Q: quit",
        "rc_okunamadi":     "could not read rubricrc: {e}",
        "rc_anlasilmadi":   "rubricrc:{no}: not understood -> {satir}",
        "rc_satir":         "rubricrc:{no}: {e}",
        "bilinmeyen_ayar":  "unknown setting: {ad}",
        "bilinmeyen_dil":   "unknown language: {dil}  (choices: {secenekler})",
        "bulunamadi":       "not found: {ne}",
        "acilamadi":        "could not open: {e}",
        "sayfa_n":          ("{n} page", "{n} pages"),
        "acildi":           "{ad} - {sayfalar}",
        "islenemedi":       "page {no} could not be rendered: {e}",
        "esleme_n":         ("{n} match", "{n} matches"),
        "arama_suruyor":    "/{desen}  {eslesme}  (scanning, {kalan} pages to go)",
        "arama_bitti":      "/{desen}  {eslesme}",
        "arama_yok":        "no search",
        "vurgu_islenemedi": "highlight could not be drawn (p{s}): {e}",
        "geri_alinacak_yok": "no highlight to undo",
        "vurgu_geri_alindi": "highlight undone",
        "vurgu_geri_geldi": "deleted highlight restored",
        "yalniz_pdf":       "highlights work in PDFs only",
        "kalem_acik":       "pen on: drag -> highlight, right click -> delete, Esc puts it down",
        "kalem_kapali":     "pen off",
        "secilecek_metin_yok": "no text to select here",
        "vurgulandi":       "highlighted: {metin}   (u: undo)",
        "vurgu_silindi":    "highlight deleted   (u: undo)",
        "belgede_vurgu_yok": "no highlights in this document  (v: pen, Shift+drag)",
        "aktarilacak_yok":  "no highlights to export",
        "aktarilamadi":     "export failed: {e}",
        "vurgulu_ek":       "highlighted",
        "vurgu_n":          ("{n} highlight", "{n} highlights"),
        "aktarildi":        "{vurgular} -> {ad}",
        "icindekiler_yok":  "no table of contents",
        "eslesme_yok":      "no matches",
        "ipucu_liste":      "enter: run   ^K: actions   esc: close",
        "ipucu_eylem":      "enter: choose   j/k: move   esc: back",
        "ipucu_kaldir":     "enter: remove   j/k: move   esc: back",
        "ipucu_yakala":     "press a key combination   esc: cancel",
        "ipucu_onay":       "enter: confirm   other key: change   esc: cancel",
        "palet_istem":      "$ rubric --actions",
        "secenek_calistir": "run",
        "secenek_tus_ata":  "bind key",
        "secenek_tus_kaldir": "remove key",
        "secenek_varsayilan": "reset to default",
        "eylemler_baslik":  "actions: {komut}",
        "hangi_tus":        "which key: {komut}",
        "yok":              "none",
        "simdiki_tuslar":   "current keys: {tuslar}",
        "yakala_bekle":     "press the key combination you want  -  esc cancels",
        "yakala_onay":      "enter confirms and writes it to rubricrc  -  another key replaces it",
        "zaten_bagli":      "{tus} is already bound to this command",
        "kilit_uyari":      "! {tus} is the last key that opens the palette, can't take it"
                            " - bind another key to actions first",
        "catisma":          "! {tus} is currently on '{sahip}', it will be taken from there",
        "sayi_tusu":        "! digit keys are read as a count prefix (5j), won't work",
        "g_tusu":           "! g starts two-key sequences (gg), alone it just waits",
        "atama_iptal":      "key binding cancelled",
        "kilit_kisa":       "{tus} is the last key that opens the palette, can't take it",
        "alindi_ek":        "  (taken from '{onceki}')",
        "rc_yazilamadi_ek": "  (could not write rubricrc)",
        "bagli_tus_yok":    "{komut}: no key bound",
        "kaldirilamaz":     "{tus} is the last key that opens the palette, can't remove it"
                            " - bind another key first",
        "varsayilana_dondu": "{komut} reset to default: {tuslar}",
        "tus_yok":          "no keys",
        "rc_yazilamadi":    "could not write rubricrc: {e}",
        "rc_bas1":          "# rubric configuration.  For every setting and every internal",
        "rc_bas2":          "# command name see rubricrc.ornek in the repository.",
        "rc_blok1":         "# The app writes this block (Ctrl-K > bind key). You can edit",
        "rc_blok2":         "# it by hand too, but the palette rebuilds it on every write.",
        "goto_kullanim":    "goto <page>",
        "zoom_kullanim":    "zoom <percent>",
        "silindi":          "deleted: {ad}",
        "bilinmeyen_komut": "unknown command: {ad}",
        "acik":             "on",
        "kapali":           "off",
        "ters_renk_durum":  "inverted colors: {durum}",
        "sutun_n":          ("{n} column", "{n} columns"),
        "ust_bar_durum":    "top bar {durum}",
        "pencere_cercevesi": "window frame: {e}",
        "ac_baslik":        "open document",
        "ac_belgeler":      "Documents",
        "ac_tumu":          "All files",
        "yer_imi":          "bookmark: {ad} (p{s})",
        "yer_imi_yok":      "no bookmarks",
        "sayfa_dosyasi":    "page-{n}.png",
        "yazildi":          "written: {yol}",
        "yazilamadi":       "could not write: {e}",
        "yazar_yok":        "no author",
        "yardim":           "j/k scroll  J/K page  gg/G start/end  s/a fit  +/- zoom  "
                            "/ search  n/N  <Tab> contents  <C-k> actions  <C-r> night  "
                            "d double  <C-Left/Right> documents  : command  q close  Q quit",
        "isaret_kondu":     "mark '{harf}",
        "isaret_yok":       "no mark: {harf}",
        "mod_icindekiler":  "[toc]",
        "mod_vurgular":     "[highlights]",
        "mod_kalem":        "[pen]",
        "bekle_isaret-koy": "[set mark]",
        "bekle_isarete-git": "[go to mark]",
        "belge_yok":        "no document",
        "sigdir_genislik":  "width",
        "sigdir_sayfa":     "page",
        "gece":             "  night",
        "dil_secildi":      "language: English",
        "dil_baslik":       "language",
        "tema_secildi":     "theme: {ad}",
        "tema_baslik":      "theme",
        "bilinmeyen_tema":  "unknown theme: {ad}  (choices: {secenekler})",
        "tek_belge":        "only one document open",
        "kapatilacak_yok":  "no document open  (Q: quit, o: open)",
        "belge_kapandi":    "closed: {ad}  ({tus}: reopen)",
        "son_belge_kapandi": "closed: {ad}  -  no documents left  ({tus}: reopen, o: open, Q: quit)",
        "geri_acildi":      "reopened: {ad}",
        "geri_acildi_daha": "reopened: {ad}  ({n} more)",
        "geri_acilacak_yok": "no closed document to reopen",
        "sinir_baslik":     "reopen limit",
        "sinir_satir":      ("{n} document", "{n} documents"),
        "sinir_varsayilan": "default",
        "sinir_secildi":    ("reopen limit: last {n} closed document",
                             "reopen limit: last {n} closed documents"),
        "belge_dustu":      "list full ({n}), dropped the longest unseen: {ad}",
        "oturum_eksik":     ("1 document of the last session is missing",
                             "{n} documents of the last session are missing"),
        "mod_belgeler":     "[documents]",
        "belge_listesi_bos": "no open documents",
        "satir_sayfa":      "p{s}",
    },
    "tr": {
        "ipucu_bos":        "o: dosya aç   <C-k>: eylemler   :open <yol>   :help   Q: çık",
        "rc_okunamadi":     "rubricrc okunamadı: {e}",
        "rc_anlasilmadi":   "rubricrc:{no}: anlaşılmadı -> {satir}",
        "bilinmeyen_ayar":  "bilinmeyen ayar: {ad}",
        "bilinmeyen_dil":   "bilinmeyen dil: {dil}  (seçenekler: {secenekler})",
        "bulunamadi":       "bulunamadı: {ne}",
        "acilamadi":        "açılamadı: {e}",
        "sayfa_n":          "{n} sayfa",
        "islenemedi":       "sayfa {no} işlenemedi: {e}",
        "esleme_n":         "{n} eşleşme",
        "arama_suruyor":    "/{desen}  {eslesme}  (taranıyor, {kalan} sayfa kaldı)",
        "arama_yok":        "arama yok",
        "vurgu_islenemedi": "vurgu işlenemedi (s{s}): {e}",
        "geri_alinacak_yok": "geri alınacak vurgu yok",
        "vurgu_geri_alindi": "vurgu geri alındı",
        "vurgu_geri_geldi": "silinen vurgu geri geldi",
        "yalniz_pdf":       "vurgu yalnızca PDF'te",
        "kalem_acik":       "kalem açık: sürükle -> vurgula, sağ tık -> sil, Esc bırak",
        "kalem_kapali":     "kalem kapalı",
        "secilecek_metin_yok": "burada seçilecek metin yok",
        "vurgulandi":       "vurgulandı: {metin}   (u: geri al)",
        "vurgu_silindi":    "vurgu silindi   (u: geri al)",
        "belgede_vurgu_yok": "bu belgede vurgu yok  (v: kalem, Shift+sürükle)",
        "aktarilacak_yok":  "aktarılacak vurgu yok",
        "aktarilamadi":     "aktarılamadı: {e}",
        "vurgulu_ek":       "vurgulu",
        "vurgu_n":          "{n} vurgu",
        "icindekiler_yok":  "içindekiler yok",
        "eslesme_yok":      "eşleşme yok",
        "ipucu_liste":      "enter: çalıştır   ^K: eylemler   esc: kapat",
        "ipucu_eylem":      "enter: seç   j/k: gez   esc: geri",
        "ipucu_kaldir":     "enter: kaldır   j/k: gez   esc: geri",
        "ipucu_yakala":     "bir tuş bileşkesine bas   esc: vazgeç",
        "ipucu_onay":       "enter: onayla   başka tuş: değiştir   esc: vazgeç",
        "palet_istem":      "$ rubric --eylemler",
        "secenek_calistir": "çalıştır",
        "secenek_tus_ata":  "tuş ata",
        "secenek_tus_kaldir": "tuşu kaldır",
        "secenek_varsayilan": "varsayılana dön",
        "eylemler_baslik":  "eylemler: {komut}",
        "hangi_tus":        "hangi tuş: {komut}",
        "yok":              "yok",
        "simdiki_tuslar":   "şimdiki tuşlar: {tuslar}",
        "yakala_bekle":     "istediğin tuş bileşkesine bas  -  esc vazgeçer",
        "yakala_onay":      "enter onaylar ve rubricrc'ye yazar  -  başka tuşa basarsan o geçer",
        "zaten_bagli":      "{tus} zaten bu komuta bağlı",
        "kilit_uyari":      "! {tus} paleti açan son tuş, alınamaz - önce eylemler'e başka tuş ata",
        "catisma":          "! {tus} şu an '{sahip}' komutunda, ondan alınacak",
        "sayi_tusu":        "! sayı tuşları sayı öneki (5j) olarak okunuyor, çalışmaz",
        "g_tusu":           "! g ikili dizilerin (gg) başı, tek başına beklemede kalır",
        "atama_iptal":      "tuş atama iptal",
        "kilit_kisa":       "{tus} paleti açan son tuş, alınamaz",
        "alindi_ek":        "  ('{onceki}' komutundan alındı)",
        "rc_yazilamadi_ek": "  (rubricrc yazılamadı)",
        "bagli_tus_yok":    "{komut}: bağlı tuş yok",
        "kaldirilamaz":     "{tus} paleti açan son tuş, kaldırılamaz - önce başka tuş ata",
        "varsayilana_dondu": "{komut} varsayılana döndü: {tuslar}",
        "tus_yok":          "tuş yok",
        "rc_yazilamadi":    "rubricrc yazılamadı: {e}",
        "rc_bas1":          "# rubric yapılandırması.  Bütün ayarlar ve tüm iç komut adları için",
        "rc_bas2":          "# depodaki rubricrc.ornek dosyasına bak.",
        "rc_blok1":         "# Bu bloğu uygulama yazar (Ctrl-K > tuş ata). Elle de",
        "rc_blok2":         "# düzenleyebilirsin ama palet her yazışında baştan üretir.",
        "goto_kullanim":    "goto <sayfa>",
        "zoom_kullanim":    "zoom <yüzde>",
        "silindi":          "silindi: {ad}",
        "bilinmeyen_komut": "bilinmeyen komut: {ad}",
        "acik":             "açık",
        "kapali":           "kapalı",
        "ters_renk_durum":  "ters renk: {durum}",
        "sutun_n":          "{n} sütun",
        "ust_bar_durum":    "üst bar {durum}",
        "pencere_cercevesi": "pencere çerçevesi: {e}",
        "ac_baslik":        "belge aç",
        "ac_belgeler":      "Belgeler",
        "ac_tumu":          "Tümü",
        "yer_imi":          "yer imi: {ad} (s{s})",
        "yer_imi_yok":      "yer imi yok",
        "sayfa_dosyasi":    "sayfa-{n}.png",
        "yazildi":          "yazıldı: {yol}",
        "yazilamadi":       "yazılamadı: {e}",
        "yazar_yok":        "yazar yok",
        "yardim":           "j/k kaydır  J/K sayfa  gg/G baş/son  s/a sığdır  +/- yakınlaştır  "
                            "/ ara  n/N  <Tab> içindekiler  <C-k> eylemler  <C-r> gece  "
                            "d çift  <C-Left/Right> belgeler  : komut  q kapat  Q çık",
        "isaret_kondu":     "işaret '{harf}",
        "isaret_yok":       "işaret yok: {harf}",
        "mod_icindekiler":  "[içindekiler]",
        "mod_vurgular":     "[vurgular]",
        "mod_kalem":        "[kalem]",
        "bekle_isaret-koy": "[işaret koy]",
        "bekle_isarete-git": "[işarete git]",
        "belge_yok":        "belge yok",
        "sigdir_genislik":  "genişlik",
        "sigdir_sayfa":     "sayfa",
        "gece":             "  gece",
        "dil_secildi":      "dil: Türkçe",
        "dil_baslik":       "dil",
        "tema_secildi":     "tema: {ad}",
        "tema_baslik":      "tema",
        "bilinmeyen_tema":  "bilinmeyen tema: {ad}  (seçenekler: {secenekler})",
        "tek_belge":        "açık tek belge bu",
        "kapatilacak_yok":  "açık belge yok  (Q: çık, o: aç)",
        "belge_kapandi":    "kapatıldı: {ad}  ({tus}: geri aç)",
        "son_belge_kapandi": "kapatıldı: {ad}  -  açık belge kalmadı  ({tus}: geri aç, o: aç, Q: çık)",
        "geri_acildi":      "geri açıldı: {ad}",
        "geri_acildi_daha": "geri açıldı: {ad}  (sırada {n} tane daha)",
        "geri_acilacak_yok": "geri açılacak kapanmış belge yok",
        "sinir_baslik":     "geri açma sınırı",
        "sinir_satir":      "{n} belge",
        "sinir_varsayilan": "varsayılan",
        "sinir_secildi":    "geri açma sınırı: kapatılan son {n} belge",
        "belge_dustu":      "liste dolu ({n}), en uzun süredir bakılmayan çıktı: {ad}",
        "oturum_eksik":     "son oturumdan {n} belge bulunamadı",
        "mod_belgeler":     "[belgeler]",
        "belge_listesi_bos": "açık belge yok",
        "satir_sayfa":      "s{s}",
    },
    "de": {
        "ipucu_bos":        "o: Datei öffnen   <C-k>: Aktionen   :open <Pfad>   :help   Q: beenden",
        "rc_okunamadi":     "rubricrc nicht lesbar: {e}",
        "rc_anlasilmadi":   "rubricrc:{no}: unverständlich -> {satir}",
        "bilinmeyen_ayar":  "unbekannte Einstellung: {ad}",
        "bilinmeyen_dil":   "unbekannte Sprache: {dil}  (möglich: {secenekler})",
        "bulunamadi":       "nicht gefunden: {ne}",
        "acilamadi":        "Öffnen fehlgeschlagen: {e}",
        "sayfa_n":          ("{n} Seite", "{n} Seiten"),
        "islenemedi":       "Seite {no} konnte nicht gerendert werden: {e}",
        "esleme_n":         ("{n} Treffer", "{n} Treffer"),
        "arama_suruyor":    "/{desen}  {eslesme}  (suche, noch {kalan} Seiten)",
        "arama_yok":        "keine Suche",
        "vurgu_islenemedi": "Markierung nicht darstellbar (S.{s}): {e}",
        "geri_alinacak_yok": "keine Markierung zum Rückgängigmachen",
        "vurgu_geri_alindi": "Markierung rückgängig gemacht",
        "vurgu_geri_geldi": "gelöschte Markierung wiederhergestellt",
        "yalniz_pdf":       "Markierungen nur in PDFs",
        "kalem_acik":       "Stift an: ziehen -> markieren, Rechtsklick -> löschen, Esc legt ihn weg",
        "kalem_kapali":     "Stift aus",
        "secilecek_metin_yok": "hier gibt es keinen Text zum Auswählen",
        "vurgulandi":       "markiert: {metin}   (u: rückgängig)",
        "vurgu_silindi":    "Markierung gelöscht   (u: rückgängig)",
        "belgede_vurgu_yok": "keine Markierungen in diesem Dokument  (v: Stift, Shift+Ziehen)",
        "aktarilacak_yok":  "keine Markierungen zum Exportieren",
        "aktarilamadi":     "Export fehlgeschlagen: {e}",
        "vurgulu_ek":       "markiert",
        "vurgu_n":          ("{n} Markierung", "{n} Markierungen"),
        "icindekiler_yok":  "kein Inhaltsverzeichnis",
        "eslesme_yok":      "keine Treffer",
        "ipucu_liste":      "enter: ausführen   ^K: Aktionen   esc: schließen",
        "ipucu_eylem":      "enter: wählen   j/k: bewegen   esc: zurück",
        "ipucu_kaldir":     "enter: entfernen   j/k: bewegen   esc: zurück",
        "ipucu_yakala":     "Tastenkombination drücken   esc: abbrechen",
        "ipucu_onay":       "enter: bestätigen   andere Taste: ändern   esc: abbrechen",
        "palet_istem":      "$ rubric --aktionen",
        "secenek_calistir": "ausführen",
        "secenek_tus_ata":  "Taste zuweisen",
        "secenek_tus_kaldir": "Taste entfernen",
        "secenek_varsayilan": "auf Standard zurück",
        "eylemler_baslik":  "Aktionen: {komut}",
        "hangi_tus":        "welche Taste: {komut}",
        "yok":              "keine",
        "simdiki_tuslar":   "aktuelle Tasten: {tuslar}",
        "yakala_bekle":     "gewünschte Tastenkombination drücken  -  esc bricht ab",
        "yakala_onay":      "enter bestätigt und schreibt in rubricrc  -  eine andere Taste ersetzt sie",
        "zaten_bagli":      "{tus} liegt bereits auf diesem Befehl",
        "kilit_uyari":      "! {tus} ist die letzte Taste für die Palette, nicht vergebbar"
                            " - erst aktionen eine andere Taste zuweisen",
        "catisma":          "! {tus} liegt gerade auf '{sahip}' und wird dort entfernt",
        "sayi_tusu":        "! Zifferntasten gelten als Zählpräfix (5j), das geht nicht",
        "g_tusu":           "! g leitet Folgen wie gg ein und wartet allein nur",
        "atama_iptal":      "Tastenzuweisung abgebrochen",
        "kilit_kisa":       "{tus} ist die letzte Taste für die Palette, nicht vergebbar",
        "alindi_ek":        "  (von '{onceki}' übernommen)",
        "rc_yazilamadi_ek": "  (rubricrc nicht geschrieben)",
        "bagli_tus_yok":    "{komut}: keine Taste zugewiesen",
        "kaldirilamaz":     "{tus} ist die letzte Taste für die Palette, nicht entfernbar"
                            " - erst eine andere Taste zuweisen",
        "varsayilana_dondu": "{komut} auf Standard zurückgesetzt: {tuslar}",
        "tus_yok":          "keine Tasten",
        "rc_yazilamadi":    "rubricrc nicht schreibbar: {e}",
        "rc_bas1":          "# rubric-Konfiguration.  Alle Einstellungen und internen Befehlsnamen",
        "rc_bas2":          "# stehen in rubricrc.ornek im Repository.",
        "rc_blok1":         "# Diesen Block schreibt die App (Ctrl-K > Taste zuweisen). Von Hand",
        "rc_blok2":         "# änderbar, aber die Palette erzeugt ihn bei jedem Schreiben neu.",
        "goto_kullanim":    "goto <Seite>",
        "zoom_kullanim":    "zoom <Prozent>",
        "silindi":          "gelöscht: {ad}",
        "bilinmeyen_komut": "unbekannter Befehl: {ad}",
        "acik":             "an",
        "kapali":           "aus",
        "ters_renk_durum":  "invertierte Farben: {durum}",
        "sutun_n":          ("{n} Spalte", "{n} Spalten"),
        "ust_bar_durum":    "Titelleiste {durum}",
        "pencere_cercevesi": "Fensterrahmen: {e}",
        "ac_baslik":        "Dokument öffnen",
        "ac_belgeler":      "Dokumente",
        "ac_tumu":          "Alle Dateien",
        "yer_imi":          "Lesezeichen: {ad} (S.{s})",
        "yer_imi_yok":      "keine Lesezeichen",
        "sayfa_dosyasi":    "seite-{n}.png",
        "yazildi":          "geschrieben: {yol}",
        "yazilamadi":       "Schreiben fehlgeschlagen: {e}",
        "yazar_yok":        "kein Autor",
        "yardim":           "j/k scrollen  J/K Seite  gg/G Anfang/Ende  s/a einpassen  +/- Zoom  "
                            "/ suchen  n/N  <Tab> Inhalt  <C-k> Aktionen  <C-r> Nacht  "
                            "d Doppelseite  <C-Left/Right> Dokumente  : Befehl  q schließen  Q beenden",
        "isaret_kondu":     "Marke '{harf}",
        "isaret_yok":       "keine Marke: {harf}",
        "mod_icindekiler":  "[Inhalt]",
        "mod_vurgular":     "[Markierungen]",
        "mod_kalem":        "[Stift]",
        "bekle_isaret-koy": "[Marke setzen]",
        "bekle_isarete-git": "[zur Marke]",
        "belge_yok":        "kein Dokument",
        "sigdir_genislik":  "Breite",
        "sigdir_sayfa":     "Seite",
        "gece":             "  Nacht",
        "dil_secildi":      "Sprache: Deutsch",
        "dil_baslik":       "Sprache",
        "tema_secildi":     "Thema: {ad}",
        "tema_baslik":      "Thema",
        "bilinmeyen_tema":  "unbekanntes Thema: {ad}  (möglich: {secenekler})",
        "tek_belge":        "nur ein Dokument offen",
        "kapatilacak_yok":  "kein Dokument offen  (Q: beenden, o: öffnen)",
        "belge_kapandi":    "geschlossen: {ad}  ({tus}: wieder öffnen)",
        "son_belge_kapandi": "geschlossen: {ad}  -  keine Dokumente mehr  ({tus}: wieder öffnen, o: öffnen, Q: beenden)",
        "geri_acildi":      "wieder geöffnet: {ad}",
        "geri_acildi_daha": "wieder geöffnet: {ad}  (noch {n})",
        "geri_acilacak_yok": "kein geschlossenes Dokument zum Wiederöffnen",
        "sinir_baslik":     "Wiederöffnen-Limit",
        "sinir_satir":      ("{n} Dokument", "{n} Dokumente"),
        "sinir_varsayilan": "Standard",
        "sinir_secildi":    ("Wiederöffnen-Limit: letztes geschlossenes Dokument",
                             "Wiederöffnen-Limit: letzte {n} geschlossene Dokumente"),
        "belge_dustu":      "Liste voll ({n}), am längsten ungesehenes entfernt: {ad}",
        "oturum_eksik":     ("1 Dokument der letzten Sitzung fehlt",
                             "{n} Dokumente der letzten Sitzung fehlen"),
        "mod_belgeler":     "[Dokumente]",
        "belge_listesi_bos": "keine offenen Dokumente",
        "satir_sayfa":      "S.{s}",
    },
}

# Varsayilan yazitipi yoksa sirayla bunlar denenir. Hepsi Turkce ve Almanca
# harflerin tamamini tasiyor (Windows'taki TTF'lerde glif glif olculdu).
YEDEK_YAZITIPLERI = ["Consolas", "Cascadia Mono", "DejaVu Sans Mono",
                     "Courier New"]


def ceviri(dil: str, anahtar: str, /, **degerler) -> str:
    """Anahtarin `dil`deki metni; yoksa Ingilizcesi, o da yoksa anahtarin kendisi."""
    kalip = METINLER.get(dil, {}).get(anahtar) or METINLER["en"].get(anahtar, anahtar)
    if isinstance(kalip, tuple):
        kalip = kalip[0] if degerler.get("n") == 1 else kalip[1]
    return kalip.format(**degerler) if degerler else kalip


def aciklama(komut: str, dil: str) -> str:
    return ACIKLAMALAR.get(dil, {}).get(komut) or ACIKLAMALAR["en"].get(komut, "")


def grup_adi(grup: str, dil: str) -> str:
    return GRUP_ADLARI.get(dil, {}).get(grup) or GRUP_ADLARI["en"].get(grup, grup)


# Palette "sigdir" yazan "sığdır"ı, "grosse" yazan "Größe"yi de bulsun:
# suzmede iki taraf da aksansiz kucuk harfe indirilir. `İ` lower()'dan once
# cevrilmeli; Python onu "i" + birlesik nokta yapar.
_KATLAMA = str.maketrans({
    "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "ç": "c", "Ç": "c",
    "ö": "o", "Ö": "o", "ü": "u", "Ü": "u", "ä": "a", "Ä": "a", "ß": "ss", "ẞ": "ss",
})


def katla(metin: str) -> str:
    return metin.translate(_KATLAMA).lower()


# Komutlarin ekranda gorunen adlari. Ic kimlik (soldaki anahtar) rubricrc'nin
# dili oldugu icin degismez ve palet dosyaya hep onu yazar; ama bu adlarin
# HER DILDEKI hali de her yerde kabul edilir: `:scroll-down`, `:aşağı`,
# rubricrc'de `map x nächste-seite`. Adlar bosluksuz (komut satirinda tek sozcuk).
KOMUT_ADLARI: dict[str, dict[str, str]] = {
    "en": {
        "asagi": "scroll-down", "yukari": "scroll-up", "sola": "scroll-left",
        "saga": "scroll-right", "yarim-asagi": "half-page-down",
        "yarim-yukari": "half-page-up", "sayfa-ileri": "page-forward",
        "sayfa-geri": "page-back", "sonraki-sayfa": "next-page",
        "onceki-sayfa": "prev-page", "ilk-sayfa": "first-page", "son-sayfa": "last-page",
        "yakinlastir": "zoom-in", "uzaklastir": "zoom-out", "sigdir-genislik": "fit-width",
        "sigdir-sayfa": "fit-page", "yakinlastirma-sifirla": "zoom-reset",
        "dondur": "rotate", "cift-sayfa": "double-page", "ters-renk": "invert-colors",
        "icindekiler": "contents", "eylemler": "actions", "tam-ekran": "fullscreen",
        "sunum": "presentation", "durum-cubugu": "status-bar", "baslik-cubugu": "top-bar",
        "dil": "language",
        "ara-ileri": "search-forward", "ara-geri": "search-backward",
        "sonraki-bulgu": "next-match", "onceki-bulgu": "prev-match",
        "vurguyu-kapat": "clear-search",
        "isaret-koy": "set-mark", "isarete-git": "go-to-mark",
        "geri-zipla": "jump-back", "ileri-zipla": "jump-forward",
        "vurgu-kalemi": "highlighter", "vurgular": "highlights",
        "vurgu-geri-al": "undo-highlight", "vurgulari-aktar": "export-highlights",
        "ac": "open-file", "yeniden-yukle": "reload", "komut-modu": "command-line",
        "cik": "quit",
        "sonraki-belge": "next-doc", "onceki-belge": "prev-doc",
        "belgeyi-kapat": "close-doc", "belgeler": "documents",
        "kapanani-ac": "reopen-closed", "geri-acma-siniri": "reopen-limit",
    },
    "tr": {
        "asagi": "aşağı", "yukari": "yukarı", "sola": "sola", "saga": "sağa",
        "yarim-asagi": "yarım-aşağı", "yarim-yukari": "yarım-yukarı",
        "sayfa-ileri": "sayfa-ileri", "sayfa-geri": "sayfa-geri",
        "sonraki-sayfa": "sonraki-sayfa", "onceki-sayfa": "önceki-sayfa",
        "ilk-sayfa": "ilk-sayfa", "son-sayfa": "son-sayfa",
        "yakinlastir": "yakınlaştır", "uzaklastir": "uzaklaştır",
        "sigdir-genislik": "sığdır-genişlik", "sigdir-sayfa": "sığdır-sayfa",
        "yakinlastirma-sifirla": "yakınlaştırma-sıfırla", "dondur": "döndür",
        "cift-sayfa": "çift-sayfa", "ters-renk": "ters-renk",
        "icindekiler": "içindekiler", "eylemler": "eylemler", "tam-ekran": "tam-ekran",
        "sunum": "sunum", "durum-cubugu": "durum-çubuğu", "baslik-cubugu": "başlık-çubuğu",
        "dil": "dil",
        "ara-ileri": "ara-ileri", "ara-geri": "ara-geri",
        "sonraki-bulgu": "sonraki-bulgu", "onceki-bulgu": "önceki-bulgu",
        "vurguyu-kapat": "vurguyu-kapat",
        "isaret-koy": "işaret-koy", "isarete-git": "işarete-git",
        "geri-zipla": "geri-zıpla", "ileri-zipla": "ileri-zıpla",
        "vurgu-kalemi": "vurgu-kalemi", "vurgular": "vurgular",
        "vurgu-geri-al": "vurgu-geri-al", "vurgulari-aktar": "vurguları-aktar",
        "ac": "aç", "yeniden-yukle": "yeniden-yükle", "komut-modu": "komut-satırı",
        "cik": "çık",
        "sonraki-belge": "sonraki-belge", "onceki-belge": "önceki-belge",
        "belgeyi-kapat": "belgeyi-kapat", "belgeler": "belgeler",
        "kapanani-ac": "kapananı-aç", "geri-acma-siniri": "geri-açma-sınırı",
    },
    "de": {
        "asagi": "runter", "yukari": "hoch", "sola": "links", "saga": "rechts",
        "yarim-asagi": "halb-runter", "yarim-yukari": "halb-hoch",
        "sayfa-ileri": "seite-vor", "sayfa-geri": "seite-zurück",
        "sonraki-sayfa": "nächste-seite", "onceki-sayfa": "vorige-seite",
        "ilk-sayfa": "erste-seite", "son-sayfa": "letzte-seite",
        "yakinlastir": "vergrößern", "uzaklastir": "verkleinern",
        "sigdir-genislik": "breite-einpassen", "sigdir-sayfa": "seite-einpassen",
        "yakinlastirma-sifirla": "zoom-zurücksetzen", "dondur": "drehen",
        "cift-sayfa": "doppelseite", "ters-renk": "farben-umkehren",
        "icindekiler": "inhalt", "eylemler": "aktionen", "tam-ekran": "vollbild",
        "sunum": "präsentation", "durum-cubugu": "statusleiste",
        "baslik-cubugu": "titelleiste", "dil": "sprache",
        "ara-ileri": "suche-vorwärts", "ara-geri": "suche-rückwärts",
        "sonraki-bulgu": "nächster-treffer", "onceki-bulgu": "voriger-treffer",
        "vurguyu-kapat": "suche-beenden",
        "isaret-koy": "marke-setzen", "isarete-git": "zur-marke",
        "geri-zipla": "zurückspringen", "ileri-zipla": "vorspringen",
        "vurgu-kalemi": "textmarker", "vurgular": "markierungen",
        "vurgu-geri-al": "markierung-rückgängig",
        "vurgulari-aktar": "markierungen-exportieren",
        "ac": "öffnen", "yeniden-yukle": "neu-laden", "komut-modu": "befehlszeile",
        "cik": "beenden",
        "sonraki-belge": "nächstes-dokument", "onceki-belge": "voriges-dokument",
        "belgeyi-kapat": "dokument-schließen", "belgeler": "dokumente",
        "kapanani-ac": "wieder-öffnen", "geri-acma-siniri": "wiederöffnen-limit",
    },
}

# ---------------------------------------------------------------------------
# Temalar (Ctrl-K > temalar). Onizlemeleri: Masaustu\rubric-temalar\.
# Her tema butun renk anahtarlarini verir; ilki bugunku varsayilanin kendisi.
# Her tema bir ic komut olur ("tema-neon"): palet, :neon, map x tema-buz.
# ---------------------------------------------------------------------------

RENK_ANAHTARLARI = ["zemin", "sayfa-cerceve", "cubuk-zemin", "cubuk-on", "vurgu",
                    "uyari", "hata", "arama-zemin", "arama-aktif", "panel-zemin",
                    "panel-secili", "sonuk", "palet-zemin", "palet-cerceve", "vurgu-rengi"]


def _tema(*renkler: str) -> dict[str, str]:
    return dict(zip(RENK_ANAHTARLARI, renkler))


TEMALAR: dict[str, dict[str, str]] = {
    "kirmizi-fosfor": {a: VARSAYILAN_AYAR[a] for a in RENK_ANAHTARLARI},
    "yesil-fosfor": _tema("#070b08", "#1b2a1e", "#0d140f", "#8fc79a", "#39ff7a", "#e3c341",
                          "#ff4d4d", "#e3c341", "#39ff7a", "#090f0a", "#16301d", "#4a6b52",
                          "#0c130e", "#22382a", "#fff176"),
    "kehribar": _tema("#0d0a05", "#2e2412", "#16110a", "#d9a95c", "#ffb000", "#ffd866",
                      "#ff5a36", "#ffd866", "#ffb000", "#110d07", "#33260f", "#6e5530",
                      "#140f08", "#3a2c14", "#ffe082"),
    "buz": _tema("#060b0e", "#16262e", "#0b1418", "#8cc3d1", "#3ee6ff", "#f2c14e",
                 "#ff5c7a", "#f2c14e", "#3ee6ff", "#081013", "#123040", "#46636e",
                 "#0a1317", "#1d3440", "#b3f5ff"),
    "neon": _tema("#0c0612", "#2a1638", "#140a1e", "#c79be0", "#ff3df2", "#ffd23f",
                  "#ff3860", "#2de2e6", "#ff3df2", "#10081a", "#321a47", "#6b4d80",
                  "#130a1c", "#3b2150", "#ff9ff3"),
    "kutup-gecesi": _tema("#1e222a", "#3b4252", "#252a33", "#c0c8d6", "#88c0d0", "#ebcb8b",
                          "#bf616a", "#ebcb8b", "#88c0d0", "#21252d", "#3b4252", "#6b7385",
                          "#242933", "#434c5e", "#ebcb8b"),
    "toprak": _tema("#1d1b17", "#3c3630", "#282520", "#d5c4a1", "#fe8019", "#fabd2f",
                    "#fb4934", "#fabd2f", "#fe8019", "#211f1a", "#45403a", "#7c6f64",
                    "#25221d", "#4a433b", "#fabd2f"),
    "murekkep": _tema("#0a0a0a", "#2a2a2a", "#141414", "#b0b0b0", "#ffffff", "#d0d0d0",
                      "#ff5555", "#9a9a9a", "#ffffff", "#0f0f0f", "#2e2e2e", "#5c5c5c",
                      "#121212", "#333333", "#cfcfcf"),
    "kagit": _tema("#e9e2d0", "#c8bda3", "#ddd4bf", "#4a4032", "#a0461f", "#9a6b00",
                   "#b3261e", "#e0b43c", "#a0461f", "#e3dac6", "#cfc3a8", "#8a7d66",
                   "#efe8d8", "#b9ab8e", "#ffe066"),
    "gun-isigi": _tema("#f2f2f0", "#cfcfcc", "#e4e4e1", "#2b2b2b", "#1f5fd1", "#a36a00",
                       "#c62828", "#ffd54a", "#1f5fd1", "#ebebe8", "#d4dcef", "#858585",
                       "#fafaf8", "#bdbdb8", "#ffd54a"),
}

# (tr ad, en ad, de ad, tr aciklama, en aciklama, de aciklama)
_TEMA_METNI = {
    "kirmizi-fosfor": ("kırmızı-fosfor", "red-phosphor", "roter-phosphor",
                       "sönük zemin, mercan vurgu (varsayılan)",
                       "dim background, coral accent (default)",
                       "gedämpfter Grund, Korallenakzent (Standard)"),
    "yesil-fosfor": ("yeşil-fosfor", "green-phosphor", "grüner-phosphor",
                     "VT220 terminali: siyah cam, yeşil ışık",
                     "VT220 terminal: black glass, green glow",
                     "VT220-Terminal: schwarzes Glas, grünes Leuchten"),
    "kehribar": ("kehribar", "amber", "bernstein",
                 "amber monitör: sıcak, göz yormayan",
                 "amber monitor: warm, easy on the eyes",
                 "Bernsteinmonitor: warm, augenschonend"),
    "buz": ("buz", "ice", "eis",
            "soğuk camgöbeği, keskin", "cold cyan, crisp", "kaltes Cyan, klar"),
    "neon": ("neon", "neon", "neon",
             "synthwave: mor gece, pembe ışık", "synthwave: purple night, pink light",
             "Synthwave: violette Nacht, pinkes Licht"),
    "kutup-gecesi": ("kutup-gecesi", "polar-night", "polarnacht",
                     "arduvaz gri-mavi, yumuşak vurgu", "slate blue-grey, soft accent",
                     "Schiefer-Blaugrau, sanfter Akzent"),
    "toprak": ("toprak", "earth", "erde",
               "kahve zemin, turuncu vurgu, retro", "brown background, orange accent, retro",
               "brauner Grund, oranger Akzent, retro"),
    "murekkep": ("mürekkep", "ink", "tinte",
                 "renksiz: siyah, gri, beyaz vurgu", "colourless: black, grey, white accent",
                 "farblos: schwarz, grau, weißer Akzent"),
    "kagit": ("kağıt", "paper", "papier",
              "açık: sepya kâğıt, kahve yazı", "light: sepia paper, brown ink",
              "hell: Sepiapapier, braune Tinte"),
    "gun-isigi": ("gün-ışığı", "daylight", "tageslicht",
                  "açık: kırık beyaz, mavi vurgu", "light: off-white, blue accent",
                  "hell: Cremeweiß, blauer Akzent"),
}
for _kimlik, (_tr, _en, _de, _atr, _aen, _ade) in _TEMA_METNI.items():
    for _dil, _ad, _acik in (("tr", _tr, _atr), ("en", _en, _aen), ("de", _de, _ade)):
        KOMUT_ADLARI[_dil][f"tema-{_kimlik}"] = _ad
        ACIKLAMALAR[_dil][f"tema-{_kimlik}"] = _acik
# Palette tek satir, en altta: Enter secim listesini acar (dil gibi). tema-<ad>
# komutlari gruplarda yok, palette gorunmez; :neon, map x tema-buz icin durur.
for _dil, _ad, _acik in (("tr", "tema", "renk teması: listeden seç (kalıcı)"),
                         ("en", "theme", "colour theme: pick from a list (persistent)"),
                         ("de", "thema", "Farbthema: aus einer Liste wählen (dauerhaft)")):
    KOMUT_ADLARI[_dil]["tema"] = _ad
    ACIKLAMALAR[_dil]["tema"] = _acik
KOMUT_GRUPLARI.append(("temalar", ["tema"]))
GRUP_ADLARI["tr"]["temalar"] = "temalar"
GRUP_ADLARI["en"]["temalar"] = "themes"
GRUP_ADLARI["de"]["temalar"] = "Themen"


def _parlaklik(onaltili: str) -> float:
    """WCAG goreli parlaklik; palette tema satirini kendi renginde yazmadan
    once okunur mu diye bakmak icin."""
    def kanal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    h = onaltili.lstrip("#")
    r, g, b = (kanal(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(a: str, b: str) -> float:
    la, lb = sorted((_parlaklik(a), _parlaklik(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# Her dildeki ad (aksansiz, kucuk harf) -> ic kimlik. "asagi" da "aşağı" da
# ayni yere cikar; testler\rc.py iki komutun ayni adi paylasmadigini denetler.
TAKMA_ADLAR: dict[str, str] = {
    katla(ad): kimlik for adlar in KOMUT_ADLARI.values() for kimlik, ad in adlar.items()}


def komut_adi(komut: str, dil: str) -> str:
    """Ic kimligin `dil`deki ekran adi (yoksa kimligin kendisi)."""
    return KOMUT_ADLARI.get(dil, {}).get(komut) or komut


def komut_kimligi(ad: str) -> str:
    """Herhangi bir dildeki komut adini ic kimlige cevirir; taninmazsa aynen."""
    if ad in ACIKLAMALAR["en"]:
        return ad
    return TAKMA_ADLAR.get(katla(ad), ad)

# Paletten yapilan tus atamalari rubricrc'nin sonunda bu isaretlerin arasinda
# toplanir; boylece kullanicinin elle yazdigi satirlara hic dokunulmaz.
RC_BLOK_BAS = "# >>> rubric: eylem paletinden yazildi >>>"
RC_BLOK_SON = "# <<< rubric <<<"


def renk(anahtar: str) -> tuple[float, float, float]:
    """`#rrggbb` ayarini PyMuPDF'in bekledigi 0-1 ucluye cevirir.

    Tus karti ile ikon betigi paleti kendi iclerinde tekrar yazmasin diye
    burada: tema degisince onlar da dondu sayilir.
    """
    ham = VARSAYILAN_AYAR[anahtar].lstrip("#")
    return tuple(int(ham[i:i + 2], 16) / 255 for i in (0, 2, 4))


def veri_dizini() -> str:
    kok = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(kok, "rubric")


def ayar_dizini() -> str:
    kok = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(kok, "rubric")


def masaustu_yolu() -> str:
    """Kullanicinin gercek masaustu klasoru (tus karti ve kisayol buraya).

    Klasorun adi dile gore degisir (Masaustu / Desktop) ve OneDrive'a
    yonlendirilmis olabilir; yolu tahmin etmek yerine Windows'a sorulur.
    """
    if sys.platform == "win32":
        tampon = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY; 0 = S_OK
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, tampon) == 0:
            return tampon.value
    return os.path.join(os.path.expanduser("~"), "Desktop")


# ---------------------------------------------------------------------------
# Yapilandirma: rubricrc
# ---------------------------------------------------------------------------

class Yapilandirma:
    """`rubricrc` dosyasini okur. Sozdizimi zathurarc'a benzer:

        # yorum
        set sayfa-arasi 18
        set ters-renk true
        map <C-n> sonraki-sayfa
        unmap d
    """

    def __init__(self):
        self.ayar = dict(VARSAYILAN_AYAR)
        self.tuslar = dict(VARSAYILAN_TUSLAR)
        # (metin anahtari, degerler): dil ayari dosyanin sonunda da olabilir,
        # o yuzden hata metne ancak okuma bitince cevrilir (hata_metinleri).
        self.hatalar: list[tuple[str, dict]] = []
        # rubricrc'de / :set ile tek tek verilen renkler: tema degisse de gecerli
        self.elle_renkler: dict[str, str] = {}

    def temayi_uygula(self) -> None:
        """Temanin renkleri, sonra elle verilenler (sira bagimsiz)."""
        self.ayar.update(TEMALAR.get(self.ayar["tema"], TEMALAR["kirmizi-fosfor"]))
        self.ayar.update(self.elle_renkler)

    def hata_metinleri(self) -> list[str]:
        return [ceviri(self.ayar["dil"], a, **d) for a, d in self.hatalar]

    @property
    def yol(self) -> str:
        return os.path.join(ayar_dizini(), "rubricrc")

    def yukle(self, yol: str | None = None) -> None:
        yol = yol or self.yol
        if not os.path.exists(yol):
            return
        try:
            # utf-8-sig: "UTF-8 with BOM" kaydedilmis dosyada ilk satir bozulmasin
            with open(yol, encoding="utf-8-sig") as f:
                icerik = f.read()
        except OSError as e:
            self.hatalar.append(("rc_okunamadi", {"e": e}))
            return

        for no, ham in enumerate(icerik.splitlines(), 1):
            satir = ham.strip()
            if not satir or satir.startswith("#"):
                continue
            parca = satir.split(None, 2)
            eylem = parca[0]
            try:
                if eylem == "set" and len(parca) >= 3:
                    self.ata(parca[1], _yorumsuz(parca[2]))
                elif eylem == "set" and len(parca) == 2:
                    self.ata(parca[1], "true")
                elif eylem == "map" and len(parca) >= 3:
                    self.tuslar[parca[1]] = _yorumsuz(parca[2]).strip()
                elif eylem == "unmap" and len(parca) >= 2:
                    self.tuslar.pop(parca[1], None)
                else:
                    self.hatalar.append(("rc_anlasilmadi", {"no": no, "satir": satir}))
            except Exception as e:  # tek satir tum dosyayi dusurmesin
                self.hatalar.append(("rc_satir", {"no": no, "e": e}))

    def ata(self, anahtar: str, deger: str) -> bool:
        """Degeri varsayilanin turune gore cevirir; boylece `set` tip bilmez.
        Kabul edilmezse hatalar'a yazar ve False doner."""
        if anahtar not in self.ayar:
            self.hatalar.append(("bilinmeyen_ayar", {"ad": anahtar}))
            return False
        simdiki = self.ayar[anahtar]
        d = deger.strip().strip('"')
        if anahtar == "dil":
            if d.lower() not in DILLER:
                self.hatalar.append(("bilinmeyen_dil", {"dil": d, "secenekler": " ".join(DILLER)}))
                return False
            self.ayar[anahtar] = d.lower()
        elif anahtar == "tema":
            kimlik = komut_kimligi(d)               # her dildeki ad da olur: neon, eis
            kimlik = kimlik[5:] if kimlik.startswith("tema-") else katla(d)
            if kimlik not in TEMALAR:
                self.hatalar.append(("bilinmeyen_tema", {"ad": d,
                                     "secenekler": " ".join(TEMALAR)}))
                return False
            self.ayar["tema"] = kimlik
            self.temayi_uygula()
        elif anahtar in RENK_ANAHTARLARI:
            self.ayar[anahtar] = self.elle_renkler[anahtar] = d
        elif anahtar == "kapanan-belgeler":
            self.ayar[anahtar] = max(1, min(KAPANAN_EN_COK, int(float(d))))
        elif isinstance(simdiki, bool):
            self.ayar[anahtar] = katla(d) in ("1", "true", "on", "yes", "evet", "acik",
                                              "ja", "an", "wahr")
        elif isinstance(simdiki, int):
            self.ayar[anahtar] = int(float(d))
        elif isinstance(simdiki, float):
            self.ayar[anahtar] = float(d)
        else:
            self.ayar[anahtar] = d
        return True


# ---------------------------------------------------------------------------
# Kalici durum: son sayfa, yer imleri, isaretler
# ---------------------------------------------------------------------------

def _yorumsuz(deger: str) -> str:
    """`set ters-renk true  # gece modu` -> `true`.

    Yorum, bosluktan sonra gelen `#` ile baslar; `#0c0909` gibi bir renk
    degerin basinda oldugu (onunde bosluk olmadigi) icin korunur. Eskiden
    yorum degere karisiyordu ve `true  # ...` sessizce false okunuyordu.
    """
    for i in range(1, len(deger)):
        if deger[i] == "#" and deger[i - 1] in " \t":
            return deger[:i].rstrip()
    return deger


class Durum:
    def __init__(self):
        self.yol = os.path.join(veri_dizini(), "durum.json")
        self.veri: dict = {}
        try:
            with open(self.yol, encoding="utf-8") as f:
                self.veri = json.load(f)
        except (OSError, ValueError):
            self.veri = {}

    def dosya(self, pdf: str) -> dict:
        return self.veri.setdefault(os.path.abspath(pdf), {})

    def yaz(self) -> None:
        try:
            os.makedirs(veri_dizini(), exist_ok=True)
            gecici = self.yol + ".tmp"
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump(self.veri, f, ensure_ascii=False, indent=1)
            os.replace(gecici, self.yol)
        except OSError:
            pass  # durum kaydi okumayi engellemez


# ---------------------------------------------------------------------------
# Uygulama
# ---------------------------------------------------------------------------

class Rubric(tk.Tk):

    def __init__(self, acilacak: str | list[str] | None = None):
        super().__init__()

        self.yapi = Yapilandirma()
        self.yapi.yukle()
        self.ayar = self.yapi.ayar
        self.tuslar = self.yapi.tuslar
        self.kalici = Durum()
        self.ayar["yazitipi"] = self.yazitipi_sec(self.ayar["yazitipi"])

        # --- belge durumu ---
        self.belge: pymupdf.Document | None = None
        self.pdf_yolu: str = ""
        # Acilis sirasindaki belge listesi (<C-Left>/<C-Right>). Yalnizca
        # yollar: bellekte hep tek belge acik (self.belge), gerisinin kaldigi
        # yer durum.json'da. Liste oturum olarak `_oturum` altinda saklanir.
        self.belgeler: list[str] = []
        # q ile kapatilanlar, en yenisi sonda: {yol, sira, konum, zoom, sigdir}
        self.kapananlar: list[dict] = []
        self.zoom: float = 1.0
        self.donme: int = 0
        self.sigdir: str = self.ayar["sigdir"]
        self.sutunlar: int = max(1, int(self.ayar["sutunlar"]))
        self.ters: bool = bool(self.ayar["ters-renk"])

        # --- gorunum durumu ---
        self.satirlar: list[dict] = []     # duzen: her satir bir sayfa grubu
        self.toplam_yukseklik: int = 0
        self.toplam_genislik: float = 0
        self._olcu: dict[int, tuple[float, float]] = {}   # sayfa -> (en, boy) pt
        # yakinlastirma: olaylar hedefi gunceller, cizim bosta bir kez yapilir
        self._hedef_zoom: float | None = None
        self._zoom_ekran: tuple[float, float] = (0.0, 0.0)
        self._zoom_isi = None
        self._komsu_isi = None
        self.onbellek: collections.OrderedDict = collections.OrderedDict()
        self.tuval_ogeleri: dict[int, int] = {}
        self.aktif_sayfa: int = 0

        # --- kip / girdi durumu ---
        self.mod: str = "normal"           # normal | komut | arama | icindekiler
        self.sayac: str = ""
        self.bekleyen: str | None = None   # g, isaret-koy, isarete-git
        self.gecici_ileti: str = ""

        # --- eylem paleti ---
        self.palet_kip: str = "liste"      # liste | eylem | kaldir | yakala | onay
        self.palet_satirlar: list = []     # liste satiri -> komut (grup basligi None)
        self.palet_secim: int = 0
        self.palet_hedef: str = ""         # tus atanan komut
        self.palet_yeni_tus: str = ""
        self.alt_ogeleri: list[str] = []   # alt menudeki secenekler
        self.alt_secim: int = 0
        self._palet_en: int = 96           # liste satirinin karakter genisligi

        # --- arama ---
        self.bulgular: list[tuple[int, pymupdf.Rect]] = []
        self.bulgu_no: int = -1
        self.son_desen: str = ""
        self.arama_yonu: int = 1
        self.arama_kuyrugu: list[int] = []
        self.arama_kimlik: int = 0      # yeni arama eskisini gecersiz kilar
        self._aktif_bulgu = None
        self._ilk_atlama = False

        # --- ziplama listesi / isaretler ---
        self.zipla_gecmis: list[float] = []
        self.zipla_ileri: list[float] = []
        self.isaretler: dict[str, float] = {}

        # --- metin vurgulari (highlight) ---
        self.vurgular: list[dict] = []     # durum.json'daki kayitlarin kendisi
        self._vurgu_xref: dict[str, int] = {}   # vurgu kimligi -> bellekteki not
        self.vurgu_gecmisi: list[tuple[str, dict]] = []   # u ile geri alma
        self.kalem: bool = False           # vurgu kalemi acik mi (v)
        self._secim: dict | None = None    # suren surukleme secimi
        self._kelimeler: dict[int, list] = {}   # sayfa -> kelime kutulari
        self.panel_konumlari: list = []    # vurgu listesinde satir -> konum

        self.komutlar = self._komut_tablosu()
        self._arayuzu_kur()
        self._baglantilari_kur()
        self._ust_bari_yerlestir()
        self.cerceveyi_uygula()

        if self.yapi.hatalar:
            self.bildir(" | ".join(self.yapi.hata_metinleri()[:2]), "uyari")

        if isinstance(acilacak, str):
            acilacak = [acilacak]
        self.oturumu_yukle(acilacak or [])

    # -- dil ve yazitipi ---------------------------------------------------

    def m(self, anahtar: str, /, **degerler) -> str:
        """Arayuz metni, secili dilde (bkz. METINLER)."""
        return ceviri(self.ayar["dil"], anahtar, **degerler)

    def ad(self, komut: str) -> str:
        """Ic komutun secili dildeki adi (ekranda gosterilen)."""
        return komut_adi(komut_kimligi(komut), self.ayar["dil"])

    def yazitipi_sec(self, istenen: str) -> str:
        """Istenen yazitipi sistemde yoksa YEDEK_YAZITIPLERI'nden ilk bulunan.

        Tk bilinmeyen bir adi sessizce kendi varsayilanina cevirir; o da
        monospace olmayabilir ve palet hizasi bozulur. Adlar buyuk/kucuk harf
        duyarsiz karsilastirilir, doner deger sistemdeki yazilisidir.
        """
        try:
            aileler = {a.lower(): a for a in tkfont.families(self)}
        except tk.TclError:
            return istenen
        for ad in [istenen, *YEDEK_YAZITIPLERI]:
            if ad.lower() in aileler:
                return aileler[ad.lower()]
        return istenen

    def dili_ayarla(self, dil: str) -> None:
        """Arayuz dilini degistirir ve rubricrc'ye kalici yazar. Kullanici
        buraya dil_menusu()'nden ya da `:lang <kod>` ile gelir."""
        diller = list(DILLER)
        dil = dil.strip().lower()
        if dil not in DILLER:
            self.bildir(self.m("bilinmeyen_dil", dil=dil, secenekler=" ".join(diller)), "hata")
            return
        self.ayar["dil"] = dil
        yazildi = self.rc_tus_yaz({}, ayarlar={"dil": dil})
        self.metinleri_tazele()
        self.bildir(self.m("dil_secildi") + ("" if yazildi else self.m("rc_yazilamadi_ek")),
                    "vurgu" if yazildi else "hata")

    def tema_uygula(self, tema: str) -> None:
        """Temayi uygular ve rubricrc'ye `set tema` olarak kalici yazar.
        rubricrc'de elle yazilmis tek tek renkler temanin ustunde kalir."""
        if tema not in TEMALAR:
            self.bildir(self.m("bilinmeyen_tema", ad=tema, secenekler=" ".join(TEMALAR)),
                        "hata")
            return
        ters, sutunlar = self.ters, self.sutunlar   # o an acilmis gece modu / cift sayfa kalsin
        self.yapi.ata("tema", tema)
        self.ayarlar_degisti()
        if (self.ters, self.sutunlar) != (ters, sutunlar):
            self.ters, self.sutunlar = ters, sutunlar
            self.onbellek.clear()
            self.yenile()
        yazildi = self.rc_tus_yaz({}, ayarlar={"tema": tema})
        self.bildir(self.m("tema_secildi", ad=self.ad(f"tema-{tema}"))
                    + ("" if yazildi else self.m("rc_yazilamadi_ek")),
                    "vurgu" if yazildi else "hata")

    def metinleri_tazele(self) -> None:
        """Dil degisince hazir duran (bir kez yazilip birakilan) metinler."""
        self.palet_alt_sol.config(text=self.m("palet_istem"))
        if self.mod == "palet":
            if self.palet_kip in ("yakala", "onay"):
                self.yakala_goster()
            elif self.palet_kip in ("eylem", "kaldir"):
                self.alt_menuyu_kapat()
            secili = self.palet_secili()
            self.palet_doldur()
            if secili:
                self._palet_komuta_git(secili)
        self.durumu_tazele()

    # -- arayuz ------------------------------------------------------------

    def _arayuzu_kur(self) -> None:
        self.title("rubric")
        # exe'de ikon paketin icinden (_MEIPASS), betikte dosyanin yanindan gelir
        ikon = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                            "rubric.ico")
        if os.path.exists(ikon):
            try:
                self.iconbitmap(default=ikon)
            except tk.TclError:
                pass
        self.geometry("1000x760")
        self.configure(bg=self.ayar["zemin"])

        yt = (self.ayar["yazitipi"], self.ayar["yazitipi-boy"])

        self.tuval = tk.Canvas(
            self, bg=self.ayar["zemin"], highlightthickness=0, bd=0,
            takefocus=True,
        )
        self.tuval.pack(side="top", fill="both", expand=True)

        # Ust bar: Windows baslik cubugunun yerine, temaya uygun. "$ rubric" istemi,
        # dosya adi ve ASCII pencere dugmeleri. Suruklenir, cift tik buyutur,
        # ust kenarindan boyutlandirilir. Gorunurlugu `baslik-cubugu` ayari.
        self.ust_bar = tk.Frame(self, bd=0)
        self.ust_cizgi = tk.Frame(self.ust_bar, height=1, bd=0)
        self.ust_cizgi.pack(side="bottom", fill="x")
        self.ust_dugmeler: dict[str, tk.Label] = {}
        for ad, metin in (("kapat", "[x]"), ("buyut", "[+]"), ("kucult", "[-]")):
            d = tk.Label(self.ust_bar, text=metin, bd=0, padx=5, pady=3, font=yt)
            d.pack(side="right")
            d.bind("<Enter>", lambda e, ad=ad: self._dugme_uzerinde(ad, True))
            d.bind("<Leave>", lambda e, ad=ad: self._dugme_uzerinde(ad, False))
            d.bind("<ButtonRelease-1>", lambda e, ad=ad: self._dugme_tiklandi(e, ad))
            self.ust_dugmeler[ad] = d
        self.ust_istem = tk.Label(self.ust_bar, text="$ rubric", bd=0, padx=8, pady=3, font=yt)
        self.ust_istem.pack(side="left")
        self.ust_ad = tk.Label(self.ust_bar, text="", anchor="w", bd=0, pady=3, font=yt)
        self.ust_ad.pack(side="left", fill="x", expand=True)
        self._ust_ad_ham = ""
        self._ust_bari_bicimle()

        # Durum cubugu: kose yuvarlatma yok, tek satir, monospace.
        self.cubuk = tk.Frame(self, bg=self.ayar["cubuk-zemin"], bd=0)
        self.cubuk.pack(side="bottom", fill="x")

        self.durum = tk.Label(
            self.cubuk, text="", anchor="w", bd=0, padx=8, pady=2,
            bg=self.ayar["cubuk-zemin"], fg=self.ayar["cubuk-on"], font=yt,
        )
        self.durum.pack(side="left", fill="x", expand=True)

        self.sag_durum = tk.Label(
            self.cubuk, text="", anchor="e", bd=0, padx=8, pady=2,
            bg=self.ayar["cubuk-zemin"], fg=self.ayar["vurgu"], font=yt,
        )
        self.sag_durum.pack(side="right")

        # Komut / arama satiri; normalde gizli, ':' veya '/' ile acilir.
        self.komut_girdi = tk.Entry(
            self, bd=0, highlightthickness=0, insertwidth=8,
            bg=self.ayar["cubuk-zemin"], fg=self.ayar["vurgu"],
            insertbackground=self.ayar["vurgu"], font=yt,
        )

        # Icindekiler paneli
        self.panel = tk.Frame(self, bg=self.ayar["panel-zemin"], bd=0)
        # exportselection kapali: baska bir widget secim yapinca Tk bu listenin
        # secimini sessizce siliyor (palet listelerinde yasandi).
        self.liste = tk.Listbox(
            self.panel, bd=0, highlightthickness=0, activestyle="none",
            exportselection=False,
            bg=self.ayar["panel-zemin"], fg=self.ayar["cubuk-on"],
            selectbackground=self.ayar["panel-secili"],
            selectforeground=self.ayar["vurgu"], font=yt,
        )
        self.liste.pack(fill="both", expand=True)
        self.icindekiler_verisi: list[int] = []
        # Enter'la gidilen baslik: (satir, gidildikten sonraki aktif sayfa)
        self._icindekiler_hatira: tuple[int, int] | None = None

        self._paleti_kur()

    def _paleti_kur(self) -> None:
        """Eylem paleti: ortada duran, uzerine binen bir kart.

        Raycast'teki duzen: ustte arama satiri, ortada komutlar ve o anki
        tuslari, sag altta secili komutun eylemleri.
        """
        yt = (self.ayar["yazitipi"], self.ayar["yazitipi-boy"])
        yt_buyuk = (self.ayar["yazitipi"], self.ayar["yazitipi-boy"] + 3)

        self.palet = tk.Frame(
            self, bg=self.ayar["palet-zemin"], bd=0, highlightthickness=1,
            highlightbackground=self.ayar["palet-cerceve"],
        )

        self.palet_ust = tk.Frame(self.palet, bg=self.ayar["palet-zemin"])
        self.palet_ust.pack(side="top", fill="x")
        self.palet_onek = tk.Label(
            self.palet_ust, text=">", bd=0, padx=9, pady=7, font=yt_buyuk,
            bg=self.ayar["palet-zemin"], fg=self.ayar["vurgu"],
        )
        self.palet_onek.pack(side="left")
        self.palet_desen = tk.StringVar()
        self.palet_girdi = tk.Entry(
            self.palet_ust, textvariable=self.palet_desen, bd=0,
            highlightthickness=0, insertwidth=8, font=yt_buyuk,
            bg=self.ayar["palet-zemin"], fg=self.ayar["cubuk-on"],
            insertbackground=self.ayar["vurgu"],
        )
        self.palet_girdi.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.palet_cizgi_ust = tk.Frame(self.palet, bg=self.ayar["palet-cerceve"],
                                        height=1)
        self.palet_cizgi_ust.pack(side="top", fill="x")

        # Alt ipucu cubugu once paketlenir; dar pencerede listeyi o kirpsin.
        self.palet_alt = tk.Frame(self.palet, bg=self.ayar["cubuk-zemin"])
        self.palet_alt.pack(side="bottom", fill="x")
        self.palet_alt_sol = tk.Label(
            self.palet_alt, text=self.m("palet_istem"), bd=0, padx=9, pady=3,
            font=yt, bg=self.ayar["cubuk-zemin"], fg=self.ayar["sonuk"],
        )
        self.palet_alt_sol.pack(side="left")
        self.palet_ipucu = tk.Label(
            self.palet_alt, text="", anchor="e", bd=0, padx=9, pady=3, font=yt,
            bg=self.ayar["cubuk-zemin"], fg=self.ayar["cubuk-on"],
        )
        self.palet_ipucu.pack(side="right")

        self.palet_liste = tk.Listbox(
            self.palet, bd=0, highlightthickness=0, activestyle="none",
            takefocus=False, exportselection=False, font=yt,
            bg=self.ayar["palet-zemin"], fg=self.ayar["cubuk-on"],
            selectbackground=self.ayar["panel-secili"],
            selectforeground=self.ayar["vurgu"],
        )
        self.palet_liste.pack(side="top", fill="both", expand=True)

        # Sag alttaki eylem menusu (ve "hangi tusu kaldirayim" listesi).
        self.alt_menu = tk.Frame(
            self.palet, bg=self.ayar["panel-zemin"], bd=0, highlightthickness=1,
            highlightbackground=self.ayar["palet-cerceve"],
        )
        self.alt_baslik = tk.Label(
            self.alt_menu, text="", anchor="w", bd=0, padx=8, pady=4, font=yt,
            bg=self.ayar["panel-zemin"], fg=self.ayar["sonuk"],
        )
        self.alt_baslik.pack(side="top", fill="x")
        # exportselection kapali: iki listbox ayni anda seciliyken Tk digerinin
        # secimini sessizce siliyor (alt menu acilinca ana liste sonuyordu).
        self.alt_liste = tk.Listbox(
            self.alt_menu, bd=0, highlightthickness=0, activestyle="none",
            takefocus=False, exportselection=False, font=yt,
            bg=self.ayar["panel-zemin"], fg=self.ayar["cubuk-on"],
            selectbackground=self.ayar["panel-secili"],
            selectforeground=self.ayar["vurgu"],
        )
        self.alt_liste.pack(side="top", fill="both", expand=True, pady=(0, 4))

        # Tus yakalama / onay ekrani - paletin ortasinda durur.
        self.yakala = tk.Frame(
            self.palet, bg=self.ayar["panel-secili"], bd=0, padx=22, pady=16,
            highlightthickness=1, highlightbackground=self.ayar["vurgu"],
        )
        self.yakala_ust = tk.Label(
            self.yakala, text="", font=yt_buyuk,
            bg=self.ayar["panel-secili"], fg=self.ayar["vurgu"],
        )
        self.yakala_ust.pack(side="top", pady=(0, 6))
        self.yakala_orta = tk.Label(
            self.yakala, text="", font=yt,
            bg=self.ayar["panel-secili"], fg=self.ayar["uyari"],
        )
        self.yakala_orta.pack(side="top")
        self.yakala_alt = tk.Label(
            self.yakala, text="", font=yt,
            bg=self.ayar["panel-secili"], fg=self.ayar["sonuk"],
        )
        self.yakala_alt.pack(side="top", pady=(8, 0))

    def _baglantilari_kur(self) -> None:
        self.bind("<Key>", self.tus_geldi)
        self.bind("<Configure>", self.pencere_degisti)
        self.tuval.bind("<MouseWheel>", self.tekerlek)
        self.tuval.bind("<Control-MouseWheel>", self.ctrl_tekerlek)
        self.tuval.bind("<Button-1>", lambda e: self.tuval.focus_set())
        # Tab'i tuval kendi sinif baglantisiyla odak gezmeye cevirir; once biz
        # yakalayip kesmezsek <Tab> hicbir zaman icindekilere ulasmaz.
        self.tuval.bind("<Tab>", self.tab_geldi)
        self.tuval.bind("<Shift-Tab>", self.tab_geldi)
        # Sol tus: kalem acik ya da Shift basiliysa metin vurgular, degilse
        # sayfayi tutup kaydirir (fare_bas karar verir). Sag tik vurguyu siler.
        self.tuval.bind("<B1-Motion>", self.fare_surukle)
        self.tuval.bind("<ButtonPress-1>", self.fare_bas)
        self.tuval.bind("<ButtonRelease-1>", self.fare_birak)
        self.tuval.bind("<Button-3>", self.sag_tik)
        self.komut_girdi.bind("<Return>", self.komut_onayla)
        self.komut_girdi.bind("<Escape>", lambda e: self.komut_iptal())
        # Palette tek odak arama satiridir; gezinme de suzme de oradan surulur.
        self.palet_girdi.bind("<Key>", self.palet_tus)
        self.palet_desen.trace_add("write", lambda *_: self.palet_suz())
        self.palet_liste.bind("<Button-1>", self.palet_fare)
        self.palet_liste.bind("<Double-Button-1>", lambda e: self.palet_calistir())
        self.alt_liste.bind("<Button-1>", self.alt_fare)
        self.alt_liste.bind("<Double-Button-1>", lambda e: self.alt_onayla())
        # Durum cubugu da ust bar da pencerenin tutamagi: surukle tasir, cift
        # tik buyutur. Ust barin ust kenari ayrica boyutlandirir.
        for w in (self.cubuk, self.durum, self.sag_durum):
            w.bind("<ButtonPress-1>", self.pencereyi_tasi)
            w.bind("<Double-Button-1>", self.buyut_kucult)
        for w in (self.ust_bar, self.ust_istem, self.ust_ad):
            w.bind("<ButtonPress-1>", self._ust_bar_basildi)
            w.bind("<Double-Button-1>", self.buyut_kucult)
            w.bind("<Motion>", self._ust_bar_imleci)
        self.ust_bar.bind("<Configure>", lambda e: self._ust_adi_sigdir())
        self.protocol("WM_DELETE_WINDOW", self.cik)
        self.tuval.focus_set()

    # -- belge -------------------------------------------------------------

    def belgeyi_ac(self, yol: str) -> None:
        yol = os.path.abspath(os.path.expanduser(yol.strip().strip('"')))
        if not os.path.exists(yol):
            self.bildir(self.m("bulunamadi", ne=yol), "hata")
            return
        try:
            yeni = pymupdf.open(yol)
        except Exception as e:
            self.bildir(self.m("acilamadi", e=e), "hata")
            return

        if self.belge is not None:
            self.konumu_kaydet()
            self.belge.close()

        self.belge = yeni
        self.pdf_yolu = yol
        self._olcu = {}
        self._icindekiler_hatira = None
        self._bekleyen_zoomu_birak()
        self.onbellek.clear()
        self.tuval_ogeleri.clear()
        self.tuval.delete("all")
        self.arama_kimlik += 1          # onceki belgenin taramasi surmesin
        self.arama_kuyrugu = []
        self.bulgular, self.bulgu_no = [], -1
        self._aktif_bulgu = None
        self.zipla_gecmis, self.zipla_ileri = [], []

        kayit = self.kalici.dosya(yol)
        self.isaretler = {k: tuple(v) for k, v in kayit.get("isaretler", {}).items()
                          if isinstance(v, (list, tuple)) and len(v) == 2}
        self._secim = None
        self._kelimeler = {}
        self.vurgu_gecmisi = []
        self._vurgulari_yukle(kayit)

        self.zoom = 1.0
        self.sigdir = self.ayar["sigdir"]
        self.donme = int(kayit.get("donme", 0)) if self.ayar["son-konum"] else 0
        self.duzeni_hesapla()

        if self.ayar["son-konum"] and "konum" in kayit:
            self.konum_imine_git(kayit["konum"], ciz=False)
        else:
            self.ofset_ata(0)
        self.ciz()

        kayit["goruldu"] = time.time()          # listeden dusecek belge buna gore secilir
        self._listeye_ekle(yol)
        dusen = self._listeyi_kirp()
        self.oturumu_kaydet()
        ileti = self.m("acildi", ad=os.path.basename(yol),
                       sayfalar=self.m("sayfa_n", n=self.belge.page_count))
        if len(self.belgeler) > 1:
            ileti = f"[{self._sira() + 1}/{len(self.belgeler)}] {ileti}"
        if dusen:
            self.bildir(self.m("belge_dustu", n=len(self.belgeler),
                               ad=os.path.basename(dusen)), "uyari")
        else:
            self.bildir(ileti, "vurgu")

    # -- belge listesi ve oturum -------------------------------------------
    #
    # zathura'daki gibi bellekte tek belge acik; ondan farkli olarak acilan
    # belgeler bir listede durur, <C-Left>/<C-Right> aralarinda gezer ve liste
    # kapanista saklanip acilista geri gelir. Gecis = o belgeyi yeniden acmak
    # (kaldigi yer, vurgulari, isaretleri durum.json'dan). Liste `son-belgeler`
    # ile sinirli; dolunca en uzun suredir bakilmayan (kayit["goruldu"]) cikar.

    @staticmethod
    def _ayni_yol(a: str, b: str) -> bool:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))

    def _sira(self, yol: str | None = None) -> int:
        yol = self.pdf_yolu if yol is None else yol
        for i, y in enumerate(self.belgeler):
            if yol and self._ayni_yol(y, yol):
                return i
        return -1

    def _listeye_ekle(self, yol: str) -> None:
        """Yeni belge listenin sonuna (en yeni); zaten varsa yeri degismez,
        yoksa <C-Left>/<C-Right> sirasi her bakista karisirdi."""
        if self._sira(yol) < 0:
            self.belgeler.append(yol)

    def _listeyi_kirp(self) -> str | None:
        """Sinir asildiysa en uzun suredir bakilmayani cikarir (bakilan haric)."""
        sinir = max(1, int(self.ayar["son-belgeler"]))
        dusen = None
        while len(self.belgeler) > sinir:
            adaylar = [y for y in self.belgeler if not self._ayni_yol(y, self.pdf_yolu)]
            if not adaylar:
                break
            dusen = min(adaylar, key=lambda y: self.kalici.dosya(y).get("goruldu", 0))
            self.belgeler.remove(dusen)
        return dusen

    def oturumu_kaydet(self) -> None:
        # kapananlar da yazilir: q'dan hemen sonra Q'ya basan geri acabilsin
        self.kalici.veri["_oturum"] = {"belgeler": list(self.belgeler),
                                       "aktif": self.pdf_yolu,
                                       "kapananlar": list(self.kapananlar)}
        self.kalici.yaz()

    def oturumu_yukle(self, acilacak: list[str]) -> None:
        """Acilis: onceki oturumun listesi + komut satirindan gelenler.
        Komut satirinda dosya verildiyse o, verilmediyse en son bakilan acilir."""
        kayit = self.kalici.veri.get("_oturum") if self.ayar["oturum"] else None
        eksik, aktif = 0, None
        if isinstance(kayit, dict):
            eski = [y for y in kayit.get("belgeler", []) if isinstance(y, str)]
            self.belgeler = [y for y in eski if os.path.exists(y)]
            eksik = len(eski) - len(self.belgeler)
            aktif = kayit.get("aktif")
            self.kapananlar = [k for k in kayit.get("kapananlar", [])
                               if isinstance(k, dict) and isinstance(k.get("yol"), str)]
            self._kapananlari_kirp()
        yeniler = [os.path.abspath(y.strip().strip('"')) for y in acilacak]
        for y in yeniler[:-1]:                  # coklu dosya: hepsi listeye, sonuncusu acilir
            if os.path.exists(y):
                self.kalici.dosya(y)["goruldu"] = time.time()
                self._listeye_ekle(y)
        if yeniler:
            hedef = yeniler[-1]
        elif aktif and self._sira(aktif) >= 0:
            hedef = aktif
        else:
            hedef = self.belgeler[-1] if self.belgeler else None
        if hedef:
            self.belgeyi_ac(hedef)
        else:
            self.bildir(self.m("ipucu_bos"), "vurgu")
        if eksik:
            self.bildir(self.m("oturum_eksik", n=eksik), "uyari")

    def belge_gez(self, yon: int) -> None:
        """<C-Right> +1 (daha yeni), <C-Left> -1 (daha eski); uclarda doner."""
        if len(self.belgeler) < 2:
            self.bildir(self.m("tek_belge"), "uyari")
            return
        i = self._sira()
        hedef = self.belgeler[(i + yon) % len(self.belgeler)] if i >= 0 else self.belgeler[-1]
        if not os.path.exists(hedef):           # bu arada silinmis / tasinmis
            self.belgeler.remove(hedef)
            self.oturumu_kaydet()
            self.bildir(self.m("bulunamadi", ne=hedef), "hata")
            return
        self.belgeyi_ac(hedef)

    def belgeyi_kapat(self, yol: str | None = None) -> None:
        """Belgeyi listeden cikarir. Bakilan belgeyse komsusu acilir; o
        sonuncuysa bos ekrana donulur."""
        yol = yol or self.pdf_yolu
        i = self._sira(yol)
        if i < 0:
            if not self.belge:          # bos ekranda q: kapatacak bir sey yok, Q'yu hatirlat
                self.bildir(self.m("kapatilacak_yok"), "uyari")
            return
        bakilan = self._ayni_yol(yol, self.pdf_yolu)
        if bakilan:
            self.konumu_kaydet()
        self._kapanani_hatirla(yol, i, bakilan)
        del self.belgeler[i]
        if bakilan:
            if self.belgeler:
                # belgeyi_ac eskisinin konumunu da yazar; listede artik yok, sorun degil
                self.belgeyi_ac(self.belgeler[min(i, len(self.belgeler) - 1)])
            else:
                self._belgeyi_birak()
        self.oturumu_kaydet()
        self.bildir(self.m("belge_kapandi" if self.belgeler else "son_belge_kapandi",
                           ad=os.path.basename(yol), tus=self._geri_ac_tusu()), "vurgu")

    # -- kapananı geri aç (<C-e>) -------------------------------------------
    #
    # q tek tus, kazara basilir. Kapanan belge bir yiginda hatirlanir; geri
    # acmak onu listedeki eski yerine, kapandigi sayfa/oran, zoom ve donmeyle
    # getirir. Yigin `kapanan-belgeler` (3) ile sinirli: art arda iki kaza
    # ve bir pay. Oturumla birlikte saklanir, q'dan sonra Q'ya basan da kurtulur.

    def _kapanani_hatirla(self, yol: str, sira: int, bakilan: bool) -> None:
        if bakilan and self.belge:
            giris = {"yol": yol, "sira": sira, "konum": list(self.konum_imi()),
                     "zoom": self.zoom, "sigdir": self.sigdir, "donme": self.donme}
        else:                                   # panelden kapatilan: durum.json'daki yeri
            kayit = self.kalici.dosya(yol)
            giris = {"yol": yol, "sira": sira, "konum": kayit.get("konum")}
        self.kapananlar = [k for k in self.kapananlar if not self._ayni_yol(k["yol"], yol)]
        self.kapananlar.append(giris)
        self._kapananlari_kirp()

    def _kapanan_siniri(self) -> int:
        return max(1, min(KAPANAN_EN_COK, int(self.ayar["kapanan-belgeler"])))

    def _kapananlari_kirp(self) -> None:
        del self.kapananlar[:max(0, len(self.kapananlar) - self._kapanan_siniri())]

    def kapanan_siniri_ayarla(self, n: int) -> None:
        """Ctrl-K > ayarlar > geri-acma-siniri. Kucultunce en eskiler hemen duser;
        rubricrc'ye `set kapanan-belgeler n` olarak kalici yazilir."""
        n = max(1, min(KAPANAN_EN_COK, int(n)))
        self.ayar["kapanan-belgeler"] = n
        self._kapananlari_kirp()
        self.oturumu_kaydet()
        yazildi = self.rc_tus_yaz({}, ayarlar={"kapanan-belgeler": str(n)})
        self.bildir(self.m("sinir_secildi", n=n) + ("" if yazildi else self.m("rc_yazilamadi_ek")),
                    "vurgu" if yazildi else "hata")

    def _geri_ac_tusu(self) -> str:
        tuslar = self.komut_tuslari().get("kapanani-ac")
        return tuslar[0] if tuslar else ":" + self.ad("kapanani-ac")

    def kapanani_ac(self) -> None:
        if not self.kapananlar:
            self.bildir(self.m("geri_acilacak_yok"), "uyari")
            return
        k = self.kapananlar.pop()
        yol = k["yol"]
        if not os.path.exists(yol):             # kapandiktan sonra silinmis / tasinmis
            self.oturumu_kaydet()
            self.bildir(self.m("bulunamadi", ne=yol), "hata")
            return
        if self._sira(yol) >= 0:                # bu arada o ile yeniden acilmis: yalnizca oraya gec
            self.belgeyi_ac(yol)
            return
        self.belgeler.insert(max(0, min(int(k.get("sira", 0)), len(self.belgeler))), yol)
        self.belgeyi_ac(yol)
        if not self._ayni_yol(yol, self.pdf_yolu):     # acilamadi, hatayi belgeyi_ac yazdi
            self.belgeler = [y for y in self.belgeler if not self._ayni_yol(y, yol)]
            self.oturumu_kaydet()
            return
        if k.get("zoom"):
            self.sigdir = k.get("sigdir", self.sigdir)
            self.zoom = max(self.ayar["en-az-yakinlastirma"],
                            min(self.ayar["en-cok-yakinlastirma"], float(k["zoom"])))
            self.donme = int(k.get("donme", self.donme))
            self._olcu = {}
            self.tuval.delete("all")
            self.tuval_ogeleri.clear()
            self.duzeni_hesapla()
        self.konum_imine_git(k.get("konum"))
        self.konumu_kaydet()
        self.oturumu_kaydet()
        ad = os.path.basename(yol)
        self.bildir(self.m("geri_acildi_daha", ad=ad, n=len(self.kapananlar))
                    if self.kapananlar else self.m("geri_acildi", ad=ad), "vurgu")

    def _belgeyi_birak(self) -> None:
        """Hic belge kalmadi: bos ekran (uygulamanin dosyasiz acilisi gibi)."""
        self.arama_kimlik += 1
        self.arama_kuyrugu = []
        self.bulgular, self.bulgu_no = [], -1
        self._aktif_bulgu = None
        self._bekleyen_zoomu_birak()
        if self.belge is not None:
            try:
                self.belge.close()
            except Exception:
                pass
        self.belge = None
        self.pdf_yolu = ""
        self.vurgular, self._vurgu_xref, self.vurgu_gecmisi = [], {}, []
        self.isaretler = {}
        self.kalem = False
        self.tuval.config(cursor="")
        self.onbellek.clear()
        self.tuval_ogeleri.clear()
        self.tuval.delete("all")
        self.satirlar = []
        self.toplam_yukseklik = 0
        self.aktif_sayfa = 0
        self.tuval.config(scrollregion=(0, 0, 0, 0))
        self.durumu_tazele()

    def belge_listesi(self) -> None:
        """Acik belgeler paneli (B): zathura'nin :open'daki son dosyalari gibi."""
        if self.mod == "belgeler":
            self.paneli_kapat()
            return
        if not self.belgeler:
            self.bildir(self.m("belge_listesi_bos"), "uyari")
            return
        if self.mod in ("icindekiler", "vurgular"):
            self.paneli_kapat()
        self.konumu_kaydet()                    # bakilanin sayfasi guncel gorunsun
        self.liste.delete(0, "end")
        self.panel_konumlari = []
        en = max(len(os.path.basename(y)) for y in self.belgeler)
        for no, y in enumerate(self.belgeler, 1):
            isaret = ">" if self._ayni_yol(y, self.pdf_yolu) else " "
            sayfa = self.m("satir_sayfa", s=int(self.kalici.dosya(y).get("sayfa", 0)) + 1)
            self.liste.insert("end", f" {isaret} {no:>2}  {os.path.basename(y):<{en}}"
                                     f"  {sayfa:>6}   {os.path.dirname(y)}")
            self.panel_konumlari.append(y)
        self.mod = "belgeler"
        self.panel.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.liste.focus_set()
        self._panel_satiri_sec(max(0, self._sira()))
        self.liste.bind("<Key>", self.panel_tus)
        self.liste.bind("<Double-Button-1>", lambda e: self.panel_sec())
        self.durumu_tazele()

    def listeden_belge_kapat(self) -> None:
        secili = self.liste.curselection()
        if not secili:
            return
        i = secili[0]
        yol = self.panel_konumlari[i]
        self.belgeyi_kapat(yol)
        if not self.belgeler:
            self.paneli_kapat()
            return
        self.mod = "normal"                     # paneli yeni listeyle bastan kur
        self.belge_listesi()
        self._panel_satiri_sec(min(i, len(self.belgeler) - 1))

    def konumu_kaydet(self) -> None:
        if not self.belge or not self.pdf_yolu:
            return
        kayit = self.kalici.dosya(self.pdf_yolu)
        kayit["konum"] = list(self.konum_imi())
        kayit["sayfa"] = self.aktif_sayfa
        kayit["donme"] = self.donme
        kayit["isaretler"] = {k: list(v) for k, v in self.isaretler.items()}
        self.kalici.yaz()

    # -- duzen -------------------------------------------------------------

    def sayfa_noktasi(self, no: int) -> tuple[float, float]:
        """Sayfanin nokta (pt) cinsinden, donme uygulanmis olcusu.

        Olcu sayfa basina bir kez okunur: `belge[no]` sayfayi MuPDF'ten
        yukler ve duzen her yakinlastirmada butun sayfalar icin kurulur
        (1612 sayfada adim basina ~85 ms buraya gidiyordu).
        """
        olcu = self._olcu.get(no)
        if olcu is None:
            r = self.belge[no].rect
            olcu = self._olcu[no] = (r.width, r.height)
        w, h = olcu
        if self.donme % 180:
            return h, w
        return w, h

    def sigdirmayi_uygula(self) -> None:
        if not self.belge or self.sigdir == "yok":
            return
        tw = max(200, self.tuval.winfo_width())
        th = max(200, self.tuval.winfo_height())
        kenar, ara = self.ayar["kenar-bosluk"], self.ayar["sayfa-arasi"]

        # Ilk satirdaki sayfalari olcut al; karisik boyutlu belgelerde de makul.
        grup = range(0, min(self.sutunlar, self.belge.page_count))
        genislikler = [self.sayfa_noktasi(i)[0] for i in grup]
        yukseklikler = [self.sayfa_noktasi(i)[1] for i in grup]
        top_w = sum(genislikler) + ara * (len(genislikler) - 1)

        if self.sigdir == "genislik":
            self.zoom = (tw - 2 * kenar) / max(1.0, top_w)
        elif self.sigdir == "sayfa":
            self.zoom = min(
                (tw - 2 * kenar) / max(1.0, top_w),
                (th - 2 * kenar) / max(1.0, max(yukseklikler)),
            )
        self.zoom = max(self.ayar["en-az-yakinlastirma"],
                        min(self.ayar["en-cok-yakinlastirma"], self.zoom))

    def duzeni_hesapla(self) -> None:
        """Sayfalari satirlara dizer; her sayfanin tuval uzerindeki yerini saptar."""
        if not self.belge:
            return
        self.sigdirmayi_uygula()

        kenar, ara = self.ayar["kenar-bosluk"], self.ayar["sayfa-arasi"]
        tw = max(200, self.tuval.winfo_width())
        self.satirlar = []
        y = kenar

        for bas in range(0, self.belge.page_count, self.sutunlar):
            grup = list(range(bas, min(bas + self.sutunlar, self.belge.page_count)))
            olcu = [(i, *self.sayfa_noktasi(i)) for i in grup]
            pikseller = [(i, int(w * self.zoom), int(h * self.zoom)) for i, w, h in olcu]
            top_w = sum(p[1] for p in pikseller) + ara * (len(pikseller) - 1)
            satir_h = max(p[2] for p in pikseller)
            x = max(kenar, (tw - top_w) / 2)

            sayfalar = []
            for no, w, h in pikseller:
                sayfalar.append({"no": no, "x": x, "y": y + (satir_h - h) // 2,
                                 "w": w, "h": h})
                x += w + ara
            self.satirlar.append({"y": y, "h": satir_h, "sayfalar": sayfalar,
                                  "genislik": top_w})
            y += satir_h + ara

        self.toplam_yukseklik = int(y - ara + kenar)
        en_genis = max([s["genislik"] for s in self.satirlar] or [tw]) + 2 * kenar
        self.toplam_genislik = max(tw, en_genis)
        self.tuval.config(scrollregion=(0, 0, self.toplam_genislik, self.toplam_yukseklik))

    def sayfa_yeri(self, no: int) -> dict | None:
        for satir in self.satirlar:
            for s in satir["sayfalar"]:
                if s["no"] == no:
                    return s
        return None

    # -- kaydirma ----------------------------------------------------------

    def ofset(self) -> float:
        return float(self.tuval.canvasy(0))

    def gorunur_yukseklik(self) -> int:
        return max(100, self.tuval.winfo_height())

    def ofset_ata(self, y: float, ciz: bool = False) -> None:
        ust_sinir = max(0, self.toplam_yukseklik - self.gorunur_yukseklik())
        y = max(0, min(ust_sinir, y))
        self.tuval.yview_moveto(y / max(1, self.toplam_yukseklik))
        if ciz:
            self.ciz()

    def kaydir(self, piksel: float) -> None:
        self.ofset_ata(self.ofset() + piksel)
        self.ciz()

    def yatay_kaydir(self, piksel: float) -> None:
        self.tuval.xview_scroll(int(piksel), "units")
        self.ciz()

    def konum_imi(self) -> tuple[int, float]:
        """Bulunulan yeri (sayfa, sayfa icindeki oran) olarak verir.

        Mutlak piksel ofseti yakinlastirma ve pencere boyu degisince anlamini
        yitirir; bu ikili zoomdan bagimsiz, dolayisiyla isaretler, ziplama
        listesi ve 'kaldigi yerden ac' hep bunun uzerinden yurur.
        """
        ust = self.ofset()
        for satir in self.satirlar:
            if satir["y"] - self.ayar["sayfa-arasi"] <= ust <= satir["y"] + satir["h"]:
                return satir["sayfalar"][0]["no"], (ust - satir["y"]) / max(1, satir["h"])
        return self.aktif_sayfa, 0.0

    def konum_imine_git(self, im, ciz: bool = True) -> None:
        if not im:
            return
        sayfa, oran = int(im[0]), float(im[1])
        yer = self.sayfa_yeri(sayfa)
        if not yer:
            return
        self.ofset_ata(yer["y"] + oran * yer["h"])
        if ciz:
            self.ciz()

    def sayfaya_git(self, no: int, zipla: bool = True) -> None:
        if not self.belge:
            return
        no = max(0, min(self.belge.page_count - 1, no))
        yer = self.sayfa_yeri(no)
        if not yer:
            return
        if zipla:
            self.zipla_kaydet()
        self.ofset_ata(yer["y"] - self.ayar["kenar-bosluk"])
        self.ciz()

    def zipla_kaydet(self) -> None:
        self.zipla_gecmis.append(self.konum_imi())
        del self.zipla_gecmis[:-100]
        self.zipla_ileri.clear()

    # -- islenmis sayfa (render) -------------------------------------------

    def sayfa_matrisi(self) -> pymupdf.Matrix:
        m = pymupdf.Matrix(self.zoom, self.zoom)
        if self.donme:
            m.prerotate(self.donme)
        return m

    def sayfa_resmi(self, no: int) -> tk.PhotoImage | None:
        anahtar = (no, round(self.zoom, 4), self.donme, self.ters)
        if anahtar in self.onbellek:
            self.onbellek.move_to_end(anahtar)
            return self.onbellek[anahtar]
        try:
            pix = self.belge[no].get_pixmap(matrix=self.sayfa_matrisi(), alpha=False)
            if self.ters:
                pix.invert_irect(pix.irect)
            resim = tk.PhotoImage(master=self, data=pix.tobytes("ppm"))
        except Exception as e:
            self.bildir(self.m("islenemedi", no=no + 1, e=e), "hata")
            return None
        self.onbellek[anahtar] = resim
        while len(self.onbellek) > max(2, int(self.ayar["onbellek"])):
            self.onbellek.popitem(last=False)
        return resim

    def ciz(self, pay: int | None = None) -> None:
        """Yalnizca goruntuye giren sayfalari isler; gerisini tuvalden dusurur.

        `pay` goruntunun ustunde / altinda onceden islenen komsuluk. Varsayilani
        yarim ekran (ani kaydirmada bosluk olmasin); yakinlastirma surerken 0.
        """
        if not self.belge:
            self.durumu_tazele()
            return

        ust = self.ofset()
        alt = ust + self.gorunur_yukseklik()
        if pay is None:
            pay = self.gorunur_yukseklik() // 2

        gorunur: set[int] = set()
        for satir in self.satirlar:
            if satir["y"] + satir["h"] < ust - pay or satir["y"] > alt + pay:
                continue
            for s in satir["sayfalar"]:
                gorunur.add(s["no"])
                if s["no"] in self.tuval_ogeleri:
                    continue
                resim = self.sayfa_resmi(s["no"])
                if resim is None:
                    continue
                oge = self.tuval.create_image(s["x"], s["y"], image=resim,
                                              anchor="nw", tags=("sayfa",))
                self.tuval.create_rectangle(
                    s["x"] - 1, s["y"] - 1, s["x"] + s["w"], s["y"] + s["h"],
                    outline=self.ayar["sayfa-cerceve"], tags=("sayfa", f"c{s['no']}"),
                )
                self.tuval_ogeleri[s["no"]] = oge

        for no in list(self.tuval_ogeleri):
            if no not in gorunur:
                self.tuval.delete(self.tuval_ogeleri.pop(no))
                self.tuval.delete(f"c{no}")

        self.aktif_sayfayi_sapta(ust)
        self.bulgulari_ciz(gorunur)
        self.durumu_tazele()

    def aktif_sayfayi_sapta(self, ust: float) -> None:
        orta = ust + self.gorunur_yukseklik() * 0.35
        for satir in self.satirlar:
            if satir["y"] <= orta <= satir["y"] + satir["h"]:
                self.aktif_sayfa = satir["sayfalar"][0]["no"]
                return
            if satir["y"] > orta:
                self.aktif_sayfa = satir["sayfalar"][0]["no"]
                return
        if self.satirlar:
            self.aktif_sayfa = self.satirlar[-1]["sayfalar"][0]["no"]

    # -- arama -------------------------------------------------------------

    def ara(self, desen: str) -> None:
        """Aramayi baslatir.

        Buyuk belgede tum sayfalari tek seferde taramak arayuzu saniyelerce
        dondurur (1600 sayfada ~20 sn olculdu). Bunun yerine tarama imlecin
        oldugu sayfadan baslayip basa saran bir kuyruga bolunur ve parca parca
        islenir: ilk esleme aninda bulunur, gerisi arka planda dolar.
        """
        if not self.belge or not desen:
            return
        self.son_desen = desen
        self.bulgular = []
        self.bulgu_no = -1
        self._aktif_bulgu = None
        self._ilk_atlama = False
        self.arama_kimlik += 1

        n = self.belge.page_count
        bas = self.aktif_sayfa
        if self.arama_yonu < 0:
            self.arama_kuyrugu = [(bas - i) % n for i in range(n)]
        else:
            self.arama_kuyrugu = [(bas + i) % n for i in range(n)]
        self._arama_adimi(self.arama_kimlik)

    # Parti buyudukce tarama hizlanir ama her parti arayuzu o sure kadar bloklar
    # (olcum: ~9 ms/sayfa). 6 sayfa ~55 ms; kaydirma akici kalsin diye bu secildi.
    def _arama_adimi(self, kimlik: int, parti: int = 6) -> None:
        if kimlik != self.arama_kimlik or not self.belge:
            return                       # yeni arama basladi ya da belge kapandi

        for no in self.arama_kuyrugu[:parti]:
            try:
                for r in self.belge[no].search_for(self.son_desen):
                    self.bulgular.append((no, r))
                    if self._aktif_bulgu is None:
                        self._aktif_bulgu = (no, r)
            except Exception:
                continue
        del self.arama_kuyrugu[:parti]

        # Liste her zaman belge sirasinda dursun ki n/N beklendigi gibi aksin;
        # uzerinde durulan esleme nesne olarak izlenir, indeksi yeniden bulunur.
        self.bulgular.sort(key=lambda b: (b[0], b[1].y0, b[1].x0))
        if self._aktif_bulgu is not None:
            self.bulgu_no = self.bulgular.index(self._aktif_bulgu)

        if self._aktif_bulgu is not None and not self._ilk_atlama:
            self._ilk_atlama = True
            self.bulguya_goster(self.bulgu_no)

        if self.arama_kuyrugu:
            eslesme = self.m("esleme_n", n=len(self.bulgular))
            self.bildir(self.m("arama_suruyor", desen=self.son_desen, eslesme=eslesme,
                               kalan=len(self.arama_kuyrugu)), "uyari")
            self.after(1, lambda: self._arama_adimi(kimlik))
        else:
            self.ciz()
            if self.bulgular:
                eslesme = self.m("esleme_n", n=len(self.bulgular))
                self.bildir(self.m("arama_bitti", desen=self.son_desen, eslesme=eslesme),
                            "vurgu")
            else:
                self.bildir(self.m("bulunamadi", ne=self.son_desen), "hata")

    def bulguya_git(self, yon: int) -> None:
        if not self.bulgular:
            self.bildir(self.m("arama_yok"), "uyari")
            return
        if self.bulgu_no < 0:
            # ekrandaki ilk sayfadan itibaren ilk eslemeyi sec
            self.bulgu_no = 0
            for i, (sayfa, _r) in enumerate(self.bulgular):
                if sayfa >= self.aktif_sayfa:
                    self.bulgu_no = i
                    break
        else:
            self.bulgu_no = (self.bulgu_no + yon) % len(self.bulgular)
        self.bulguya_goster(self.bulgu_no)

    def bulguya_goster(self, no: int) -> None:
        if not (0 <= no < len(self.bulgular)):
            return
        self.bulgu_no = no
        self._aktif_bulgu = self.bulgular[no]
        sayfa, r = self.bulgular[no]
        yer = self.sayfa_yeri(sayfa)
        if yer:
            self.zipla_kaydet()
            d = self.aygit_dikdortgeni(sayfa, r, yer)
            self.ofset_ata(d[1] - self.gorunur_yukseklik() * 0.35)
        self.ciz()

    def aygit_dikdortgeni(self, sayfa: int, r: pymupdf.Rect, yer: dict) -> tuple:
        """PDF nokta uzayindaki dikdortgeni tuval koordinatina cevirir."""
        m = self.sayfa_matrisi()
        sinir = self.belge[sayfa].rect * m
        d = r * m
        return (yer["x"] + (d.x0 - sinir.x0), yer["y"] + (d.y0 - sinir.y0),
                yer["x"] + (d.x1 - sinir.x0), yer["y"] + (d.y1 - sinir.y0))

    def bulgulari_ciz(self, gorunur: set[int]) -> None:
        self.tuval.delete("bulgu")
        if not self.bulgular:
            return
        aktif = self.bulgular[self.bulgu_no] if 0 <= self.bulgu_no < len(self.bulgular) else None
        for i, (sayfa, r) in enumerate(self.bulgular):
            if sayfa not in gorunur:
                continue
            yer = self.sayfa_yeri(sayfa)
            if not yer:
                continue
            x0, y0, x1, y1 = self.aygit_dikdortgeni(sayfa, r, yer)
            bu_aktif = aktif is not None and i == self.bulgu_no
            renk = self.ayar["arama-aktif"] if bu_aktif else self.ayar["arama-zemin"]
            self.tuval.create_rectangle(
                x0 - 1, y0 - 1, x1 + 1, y1 + 1, outline=renk, width=1,
                fill=renk, stipple="gray25", tags=("bulgu",),
            )

    def vurguyu_kapat(self) -> None:
        self.arama_kimlik += 1          # suren taramayi da durdurur
        self.arama_kuyrugu = []
        self.bulgular, self.bulgu_no = [], -1
        self._aktif_bulgu = None
        self.tuval.delete("bulgu")
        if self.kalem:                  # Esc kalemi de birakir (vurgulara dokunmaz)
            self.kalem = False
            self.tuval.config(cursor="")
        self.gecici_ileti = ""
        self.durumu_tazele()

    # -- metin vurgulari ---------------------------------------------------
    #
    # Vurgular PDF dosyasina YAZILMAZ: durum.json'da, sayfa nokta uzayinda
    # (zoom ve dondurmeden bagimsiz) dikdortgenler olarak durur. Cizim icin
    # bellekteki belgeye gercek bir highlight notu eklenir; MuPDF onu sayfayla
    # birlikte "carpma" karisimiyla isler, yani yazi kalemin altinda okunur
    # kalir. Dosyaya yalnizca `vurgulari-aktar` yazar, o da ayri bir kopyaya.

    def _vurgulari_yukle(self, kayit: dict) -> None:
        self._vurgu_xref = {}
        self.vurgular = [v for v in kayit.get("vurgular", [])
                         if isinstance(v, dict) and v.get("dikler") and v.get("kimlik")
                         and 0 <= int(v.get("sayfa", -1)) < self.belge.page_count]
        for v in self.vurgular:
            self._notu_ekle(v)

    def _vurgulari_kaydet(self) -> None:
        """Hemen diske: uygulama cokerse de vurgu kaybolmasin."""
        kayit = self.kalici.dosya(self.pdf_yolu)
        if self.vurgular:
            kayit["vurgular"] = self.vurgular
        else:
            kayit.pop("vurgular", None)
        self.kalici.yaz()

    def _vurgulari_yeniden_isle(self) -> None:
        """Renk degisince (:set vurgu-rengi) bellekteki notlari bastan kurar."""
        if not self.belge or not self.belge.is_pdf:
            return
        for v in self.vurgular:
            self._notu_sil(v)
            self._notu_ekle(v)

    def _notu_ekle(self, v: dict) -> bool:
        """Vurguyu bellekteki belgeye highlight notu olarak isler."""
        if not self.belge.is_pdf:
            return False
        try:
            sayfa = self.belge[int(v["sayfa"])]
            dortgenler = [pymupdf.Rect(d).quad for d in v["dikler"]]
            not_ = sayfa.add_highlight_annot(quads=dortgenler)
            r = self.ayar["vurgu-rengi"].lstrip("#")
            not_.set_colors(stroke=[int(r[i:i + 2], 16) / 255 for i in (0, 2, 4)])
            not_.set_info(title="rubric", subject=v["kimlik"], content=v.get("metin", ""))
            not_.update()
            self._vurgu_xref[v["kimlik"]] = not_.xref
            return True
        except Exception as e:
            self.bildir(self.m("vurgu_islenemedi", s=int(v.get("sayfa", 0)) + 1, e=e), "hata")
            return False

    def _notu_sil(self, v: dict) -> None:
        xref = self._vurgu_xref.pop(v["kimlik"], None)
        if xref is None:
            return
        sayfa = self.belge[int(v["sayfa"])]
        for not_ in sayfa.annots():
            if not_.xref == xref:
                sayfa.delete_annot(not_)
                break

    def _sayfayi_tazele(self, no: int) -> None:
        """Tek sayfanin islenmis resmini atar; ciz() onu yeniden isler."""
        for anahtar in [a for a in self.onbellek if a[0] == no]:
            del self.onbellek[anahtar]
        if no in self.tuval_ogeleri:
            self.tuval.delete(self.tuval_ogeleri.pop(no))
            self.tuval.delete(f"c{no}")
        self.ciz()

    def _vurgu_ekle(self, v: dict, gecmise: bool = True) -> None:
        self.vurgular.append(v)
        self._notu_ekle(v)
        if gecmise:
            self.vurgu_gecmisi.append(("ekle", v))
        self._vurgulari_kaydet()
        self._sayfayi_tazele(int(v["sayfa"]))

    def _vurgu_sil(self, v: dict, gecmise: bool = True) -> None:
        if v not in self.vurgular:
            return
        self.vurgular.remove(v)
        self._notu_sil(v)
        if gecmise:
            self.vurgu_gecmisi.append(("sil", v))
        self._vurgulari_kaydet()
        self._sayfayi_tazele(int(v["sayfa"]))

    def vurgu_geri_al(self) -> None:
        if not self.vurgu_gecmisi:
            self.bildir(self.m("geri_alinacak_yok"), "uyari")
            return
        islem, v = self.vurgu_gecmisi.pop()
        if islem == "ekle":
            self._vurgu_sil(v, gecmise=False)
            self.bildir(self.m("vurgu_geri_alindi"), "vurgu")
        else:
            self._vurgu_ekle(v, gecmise=False)
            self.bildir(self.m("vurgu_geri_geldi"), "vurgu")

    def vurgu_kalemi(self) -> None:
        if not self.belge:
            return
        if not self.belge.is_pdf:
            self.bildir(self.m("yalniz_pdf"), "uyari")
            return
        self.kalem = not self.kalem
        self.tuval.config(cursor="xterm" if self.kalem else "")
        self.bildir(self.m("kalem_acik" if self.kalem else "kalem_kapali"), "vurgu")

    # -- vurgu: fare ve secim ---------------------------------------------

    def _tuval_noktasi(self, olay) -> tuple[float, float]:
        return self.tuval.canvasx(olay.x), self.tuval.canvasy(olay.y)

    def _noktadaki_sayfa(self, x: float, y: float) -> dict | None:
        for satir in self.satirlar:
            if satir["y"] <= y <= satir["y"] + satir["h"]:
                for s in satir["sayfalar"]:
                    if s["x"] <= x <= s["x"] + s["w"] and s["y"] <= y <= s["y"] + s["h"]:
                        return s
        return None

    def _sayfa_noktasina(self, yer: dict, x: float, y: float) -> pymupdf.Point:
        """Tuval koordinati -> sayfanin nokta uzayi (aygit_dikdortgeni'nin tersi)."""
        m = self.sayfa_matrisi()
        sinir = self.belge[yer["no"]].rect * m
        return pymupdf.Point(x - yer["x"] + sinir.x0, y - yer["y"] + sinir.y0) * ~m

    def _sayfa_kelimeleri(self, no: int) -> list:
        if no not in self._kelimeler:
            try:
                self._kelimeler[no] = self.belge[no].get_text("words")
            except Exception:
                self._kelimeler[no] = []
        return self._kelimeler[no]

    @staticmethod
    def _en_yakin_kelime(kelimeler: list, p: pymupdf.Point) -> int:
        en_iyi, secilen = float("inf"), -1
        for i, k in enumerate(kelimeler):
            dx = max(k[0] - p.x, 0.0, p.x - k[2])
            dy = max(k[1] - p.y, 0.0, p.y - k[3])
            uzaklik = dx * dx + 4 * dy * dy        # satir disi daha uzak sayilsin
            if uzaklik < en_iyi:
                en_iyi, secilen = uzaklik, i
        return secilen

    def _secim_dikleri(self) -> tuple[list[list[float]], str]:
        """Suren secimin satir satir dikdortgenleri ve metni."""
        s = self._secim
        kelimeler = self._sayfa_kelimeleri(s["sayfa"])
        if s["bas"] < 0 or s["son"] < 0:
            return [], ""
        a, b = sorted((s["bas"], s["son"]))
        dikler: list[list[float]] = []
        parcalar: list[str] = []
        onceki_satir = None
        for k in kelimeler[a:b + 1]:
            satir = (k[5], k[6])                    # (blok, satir)
            if satir == onceki_satir:
                d = dikler[-1]
                d[0], d[1] = min(d[0], k[0]), min(d[1], k[1])
                d[2], d[3] = max(d[2], k[2]), max(d[3], k[3])
                parcalar[-1] += " " + k[4]
            else:
                dikler.append([k[0], k[1], k[2], k[3]])
                parcalar.append(k[4])
            onceki_satir = satir
        return [[round(c, 2) for c in d] for d in dikler], " ".join(parcalar)

    def secim_basla(self, olay) -> None:
        x, y = self._tuval_noktasi(olay)
        yer = self._noktadaki_sayfa(x, y)
        if not yer or not self.belge.is_pdf:
            self._secim = None
            return
        kelimeler = self._sayfa_kelimeleri(yer["no"])
        i = self._en_yakin_kelime(kelimeler, self._sayfa_noktasina(yer, x, y))
        self._secim = {"sayfa": yer["no"], "yer": yer, "bas": i, "son": i,
                       "x": x, "y": y, "oynadi": False}

    def secim_surukle(self, olay) -> None:
        s = self._secim
        if not s:
            return
        x, y = self._tuval_noktasi(olay)
        if abs(x - s["x"]) + abs(y - s["y"]) > 4:
            s["oynadi"] = True
        yer = s["yer"]                            # secim tek sayfada kalir
        x = max(yer["x"], min(yer["x"] + yer["w"], x))
        y = max(yer["y"], min(yer["y"] + yer["h"], y))
        s["son"] = self._en_yakin_kelime(self._sayfa_kelimeleri(s["sayfa"]),
                                         self._sayfa_noktasina(yer, x, y))
        self._secimi_ciz()

    def _secimi_ciz(self) -> None:
        self.tuval.delete("secim")
        s = self._secim
        if not s or not s["oynadi"]:
            return
        yer = self.sayfa_yeri(s["sayfa"]) or s["yer"]
        renk = self.ayar["vurgu-rengi"]
        for d in self._secim_dikleri()[0]:
            x0, y0, x1, y1 = self.aygit_dikdortgeni(s["sayfa"], pymupdf.Rect(d), yer)
            self.tuval.create_rectangle(x0, y0, x1, y1, outline=renk, fill=renk,
                                        stipple="gray50", tags=("secim",))

    def secim_bitir(self, olay=None) -> None:
        s, self._secim = self._secim, None
        self.tuval.delete("secim")
        if not s or not s["oynadi"]:
            return                                # tik: vurgu yok (kaza olmasin)
        self._secim = s
        dikler, metin = self._secim_dikleri()
        self._secim = None
        if not dikler:
            self.bildir(self.m("secilecek_metin_yok"), "uyari")
            return
        v = {"kimlik": f"{time.time_ns():x}", "sayfa": s["sayfa"], "dikler": dikler,
             "metin": metin, "zaman": time.strftime("%Y-%m-%d %H:%M")}
        self._vurgu_ekle(v)
        kisa = metin if len(metin) <= 48 else metin[:45] + "..."
        self.bildir(self.m("vurgulandi", metin=kisa), "vurgu")

    def noktadaki_vurgu(self, x: float, y: float) -> dict | None:
        yer = self._noktadaki_sayfa(x, y)
        if not yer:
            return None
        p = self._sayfa_noktasina(yer, x, y)
        for v in reversed(self.vurgular):          # ustteki (son eklenen) once
            if int(v["sayfa"]) == yer["no"] and any(
                    pymupdf.Rect(d).contains(p) for d in v["dikler"]):
                return v
        return None

    def sag_tik(self, olay) -> str:
        v = self.noktadaki_vurgu(*self._tuval_noktasi(olay))
        if v:
            self._vurgu_sil(v)
            self.bildir(self.m("vurgu_silindi"), "vurgu")
        return "break"

    # tuvalde sol tus: kalem acik ya da Shift basiliysa secim, degilse kaydirma

    def fare_bas(self, olay) -> None:
        self.tuval.focus_set()
        if self.belge and self.belge.is_pdf and (self.kalem or olay.state & 0x1):
            self.secim_basla(olay)
        else:
            self._secim = None
            self.surukle_basla(olay)

    def fare_surukle(self, olay) -> None:
        if self._secim is not None:
            self.secim_surukle(olay)
        else:
            self.surukle(olay)

    def fare_birak(self, olay) -> None:
        if self._secim is not None:
            self.secim_bitir(olay)

    # -- vurgu: liste ve disa aktarma -------------------------------------

    def vurgu_listesi(self) -> None:
        if not self.belge:
            return
        if self.mod == "vurgular":
            self.paneli_kapat()
            return
        if not self.vurgular:
            self.bildir(self.m("belgede_vurgu_yok"), "uyari")
            return
        if self.mod in ("icindekiler", "belgeler"):
            self.paneli_kapat()
        sirali = sorted(self.vurgular, key=lambda v: (int(v["sayfa"]), v["dikler"][0][1]))
        self.liste.delete(0, "end")
        self.panel_konumlari = []
        for v in sirali:
            metin = " ".join(v.get("metin", "").split())
            self.liste.insert("end", f"  [{int(v['sayfa']) + 1:>4}]  {metin}")
            self.panel_konumlari.append(v)
        self.mod = "vurgular"
        self.panel.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.liste.focus_set()
        secim = 0
        for i, v in enumerate(sirali):
            if int(v["sayfa"]) <= self.aktif_sayfa:
                secim = i
        self._panel_satiri_sec(secim)
        self.liste.bind("<Key>", self.panel_tus)
        self.liste.bind("<Double-Button-1>", lambda e: self.panel_sec())
        self.durumu_tazele()

    def _vurguya_git(self, v: dict) -> None:
        yer = self.sayfa_yeri(int(v["sayfa"]))
        if not yer:
            return
        self.zipla_kaydet()
        d = self.aygit_dikdortgeni(int(v["sayfa"]), pymupdf.Rect(v["dikler"][0]), yer)
        self.ofset_ata(d[1] - self.gorunur_yukseklik() * 0.35)
        self.ciz()

    def vurgulari_aktar(self) -> None:
        if not self.belge or not self.pdf_yolu:
            return
        if not self.belge.is_pdf:
            self.bildir(self.m("yalniz_pdf"), "uyari")
            return
        if not self.vurgular:
            self.bildir(self.m("aktarilacak_yok"), "uyari")
            return
        kok, _ = os.path.splitext(self.pdf_yolu)
        ek = self.m("vurgulu_ek")                 # <ad>-highlighted.pdf / -vurgulu / -markiert
        hedef, n = f"{kok}-{ek}.pdf", 2
        while os.path.exists(hedef):              # var olan bir dosyanin ustune yazma
            hedef, n = f"{kok}-{ek}-{n}.pdf", n + 1
        try:
            self.belge.save(hedef, garbage=1, deflate=True)
        except Exception as e:
            self.bildir(self.m("aktarilamadi", e=e), "hata")
            return
        self.bildir(self.m("aktarildi", vurgular=self.m("vurgu_n", n=len(self.vurgular)),
                           ad=os.path.basename(hedef)), "vurgu")

    # -- icindekiler -------------------------------------------------------

    def icindekiler(self) -> None:
        if not self.belge:
            return
        if self.mod == "icindekiler":
            self.paneli_kapat()
            return
        if self.mod in ("vurgular", "belgeler"):
            self.paneli_kapat()
        toc = self.belge.get_toc()
        if not toc:
            self.bildir(self.m("icindekiler_yok"), "uyari")
            return
        self.liste.delete(0, "end")
        self.icindekiler_verisi = []
        for derinlik, baslik, sayfa in toc:
            girinti = "  " * max(0, derinlik - 1)
            isaret = "+ " if derinlik == 1 else "- "
            self.liste.insert("end", f"{girinti}{isaret}{baslik}  [{sayfa}]")
            self.icindekiler_verisi.append(max(0, sayfa - 1))

        self.mod = "icindekiler"
        self.panel.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.liste.focus_set()
        self._panel_satiri_sec(self._icindekiler_baslangici())
        self.liste.bind("<Key>", self.panel_tus)
        self.liste.bind("<Double-Button-1>", lambda e: self.panel_sec())
        self.durumu_tazele()

    def _icindekiler_baslangici(self) -> int:
        """Panel acilinca secilecek satir.

        Enter'la gidilen baslik, o sayfadan ayrilmadikca hatirlanir: ayni
        sayfada birden cok alt bolum baslayabilir (1.2 / 1.2.1 / 1.2.2) ve
        sayfadan tahmin edilen satir secilenden farkli cikar. Sayfa
        degistiyse bulunulan sayfada / ondan once baslayan en son baslik.
        """
        hatira = self._icindekiler_hatira
        if (hatira and hatira[1] == self.aktif_sayfa
                and hatira[0] < len(self.icindekiler_verisi)):
            return hatira[0]
        secim, en_iyi = 0, -1
        for i, s in enumerate(self.icindekiler_verisi):
            if en_iyi <= s <= self.aktif_sayfa:     # esitlikte sonraki: en alttaki
                secim, en_iyi = i, s
        return secim

    def _panel_satiri_sec(self, i: int) -> None:
        """Satiri sec. `activate` da sart: oklar (Tk'nin listbox baglantisi)
        secimden degil aktif satirdan yurur; aktif hep 0'da kalinca ilk ok
        basisi listenin basina atliyordu."""
        n = self.liste.size()
        if not n:
            return
        i = max(0, min(n - 1, i))
        self.liste.selection_clear(0, "end")
        self.liste.selection_set(i)
        self.liste.activate(i)
        self.liste.see(i)

    def panel_tus(self, olay) -> str | None:
        ad = self.tus_adini_coz(olay)
        # bir ekranda kac satir var (PageUp / PageDown icin)
        ekran = max(1, self.liste.nearest(self.liste.winfo_height()) - self.liste.nearest(0))
        adim = {"j": 1, "<Down>": 1, "k": -1, "<Up>": -1,
                "<Next>": ekran, "<Prior>": -ekran}.get(ad)
        if ad in ("<Esc>", "<Tab>", "<S-Tab>", "q"):
            self.paneli_kapat()
        elif ad in ("<Return>", "l"):
            self.panel_sec()
        elif adim is not None:
            self.panel_gez(adim)
        elif ad in ("g", "<Home>"):
            self._panel_satiri_sec(0)
        elif ad in ("G", "<End>"):
            self._panel_satiri_sec(self.liste.size() - 1)
        elif ad in ("x", "<Delete>") and self.mod == "vurgular":
            self.listeden_vurgu_sil()
        elif ad == "V" and self.mod == "vurgular":
            self.paneli_kapat()
        elif ad in ("x", "<Delete>") and self.mod == "belgeler":
            self.listeden_belge_kapat()
        elif ad == "B" and self.mod == "belgeler":
            self.paneli_kapat()
        else:
            return None
        return "break"

    def listeden_vurgu_sil(self) -> None:
        secili = self.liste.curselection()
        if not secili:
            return
        i = secili[0]
        v = self.panel_konumlari.pop(i)
        self._vurgu_sil(v)
        self.liste.delete(i)
        if not self.panel_konumlari:
            self.paneli_kapat()
        else:
            self._panel_satiri_sec(i)
        self.bildir(self.m("vurgu_silindi"), "vurgu")

    def panel_gez(self, yon: int) -> None:
        secili = self.liste.curselection()
        # secim yoksa (fareyle bosa tiklanmis) aktif satirdan devam
        self._panel_satiri_sec((secili[0] if secili else self.liste.index("active")) + yon)

    def panel_sec(self) -> None:
        secili = self.liste.curselection()
        if not secili:
            return
        if self.mod == "vurgular":
            v = self.panel_konumlari[secili[0]]
            self.paneli_kapat()
            self._vurguya_git(v)
        elif self.mod == "belgeler":
            yol = self.panel_konumlari[secili[0]]
            self.paneli_kapat()
            if not self._ayni_yol(yol, self.pdf_yolu):
                self.belgeyi_ac(yol)
        else:
            hedef = self.icindekiler_verisi[secili[0]]
            self.paneli_kapat()
            self.sayfaya_git(hedef)
            # bu sayfadan ayrilmadikca Tab ayni basliktan acilsin
            self._icindekiler_hatira = (secili[0], self.aktif_sayfa)

    def paneli_kapat(self) -> None:
        self.panel.place_forget()
        self.mod = "normal"
        self.tuval.focus_set()
        self.durumu_tazele()

    # -- eylem paleti ------------------------------------------------------
    #
    # Ctrl-K butun ic komutlari, ne ise yaradiklarini ve o anki tuslarini tek
    # listede acar. Secili komutun uzerinde yine Ctrl-K eylem menusunu getirir:
    # calistir / tus ata / tusu kaldir / varsayilana don. "tus ata" bir tus
    # bileskesi bekler, onaylatir ve atamayi rubricrc'ye kalici yazar - boylece
    # tus degistirmek icin dosya bulup elle duzenlemek gerekmez.

    def eylemler(self) -> None:
        if self.mod == "palet":
            self.paleti_kapat()
            return
        if self.mod in ("icindekiler", "vurgular", "belgeler"):
            self.paneli_kapat()
        elif self.mod in ("komut", "arama"):
            self.komut_iptal()

        self.mod = "palet"
        self.palet_kip = "liste"
        self.palet_hedef = ""
        self.palet_yeni_tus = ""
        self.palet_secim = 0
        self.palet_desen.set("")        # izleyici palet_suz'u tetikler ama
        self.palet.place(relx=0.5, rely=0.5, anchor="center",
                         relwidth=0.82, relheight=0.76)
        self.palet.lift()
        self.palet_girdi.focus_set()
        self.update_idletasks()         # genisligi olcebilmek icin yerlessin
        self._palet_genisligini_olc()
        self.palet_doldur()             # asil dolduran bu
        self.durumu_tazele()

    def paleti_kapat(self) -> None:
        self.alt_menuyu_kapat()
        self.yakala.place_forget()
        self.palet.place_forget()
        self.palet_kip = "liste"
        self.mod = "normal"
        self.tuval.focus_set()
        self.durumu_tazele()

    def komut_tuslari(self) -> dict[str, list[str]]:
        """komut -> o komuta bagli tuslar; once tek karakterliler."""
        ters: dict[str, list[str]] = {}
        for tus, komut in self.tuslar.items():
            # rubricrc'de `map x next-page` de yazilabilir; ic kimlige topla
            ters.setdefault(komut_kimligi(komut), []).append(tus)
        for liste in ters.values():
            liste.sort(key=lambda t: (t.startswith("<"), t.lower(), t))
        return ters

    def varsayilan_tuslar(self, komut: str) -> list[str]:
        return [t for t, k in VARSAYILAN_TUSLAR.items() if k == komut]

    # -- palet: liste ------------------------------------------------------

    def _palet_genisligini_olc(self) -> None:
        """Satirin kac karakter tuttugunu pikselden hesaplar.

        Tus sutunu saga yaslanacak; monospace bile olsa bunu goz karari
        yapmak dar pencerede tasmaya yol aciyor.
        """
        try:
            olcu = tkfont.Font(font=self.palet_liste.cget("font")).measure("0")
        except tk.TclError:
            olcu = 0
        en = self.palet_liste.winfo_width()
        self._palet_en = max(52, (en - 14) // max(6, olcu)) if en > 1 else 96

    def _palet_satiri(self, komut: str, aciklama: str, tuslar: str) -> str:
        """`komut` ic kimlik; satira secili dildeki adi yazilir. Ad sutunu o
        dilin en uzun adina gore (Almanca "markierungen-exportieren" 24 harf)."""
        en = self._palet_en
        adlar = KOMUT_ADLARI.get(self.ayar["dil"], {})
        sutun = max([len(a) for a in adlar.values()] + [22]) + 2
        sol = f"  {komut_adi(komut, self.ayar['dil']):<{sutun}}{aciklama}"
        if len(sol) + len(tuslar) + 2 > en:
            sol = sol[:max(0, en - len(tuslar) - 3)] + "~"
        return sol + tuslar.rjust(max(2, en - len(sol)))

    def palet_suz(self, *_) -> None:
        if self.mod == "palet" and self.palet_kip == "liste":
            self.palet_doldur()

    def palet_doldur(self) -> None:
        desen = katla(self.palet_desen.get().strip())
        harita = self.komut_tuslari()
        dil = self.ayar["dil"]
        self.palet_liste.delete(0, "end")
        self.palet_satirlar = []

        for grup, komutlar in KOMUT_GRUPLARI:
            grup_ad = grup_adi(grup, dil)
            uyanlar = []
            for komut in komutlar:
                if komut not in self.komutlar:
                    continue
                metin = aciklama(komut, dil)
                tuslar = "  ".join(harita.get(komut, []))
                # Adin ve aciklamanin her dildeki hali aranir: arayuz
                # Ingilizceyken "gece" ya da "aşağı" yazan da bulsun.
                butun = " ".join(f"{komut_adi(komut, d)} {aciklama(komut, d)}"
                                 for d in DILLER)
                if desen and desen not in katla(f"{komut} {tuslar} {grup_ad} {butun}"):
                    continue
                uyanlar.append((komut, metin, tuslar))
            if not uyanlar:
                continue
            self._palet_ekle(f" [ {grup_ad} ]", None, self.ayar["sonuk"])
            for komut, metin, tuslar in uyanlar:
                self._palet_ekle(self._palet_satiri(komut, metin, tuslar), komut)

        if not any(k for k in self.palet_satirlar):
            self._palet_ekle("  " + self.m("eslesme_yok"), None, self.ayar["uyari"])
        self.palet_sec(0, 1)
        self.palet_ipucunu_tazele()

    def _palet_ekle(self, metin: str, komut: str | None, renk: str = "") -> None:
        self.palet_liste.insert("end", metin)
        if renk:
            self.palet_liste.itemconfig(self.palet_liste.size() - 1, foreground=renk)
        self.palet_satirlar.append(komut)

    def _palet_adaylar(self) -> list[int]:
        return [i for i, k in enumerate(self.palet_satirlar) if k is not None]

    def palet_sec(self, i: int, yon: int = 1) -> None:
        adaylar = self._palet_adaylar()
        self.palet_liste.selection_clear(0, "end")
        if not adaylar:
            self.palet_secim = -1
            return
        i = max(0, min(len(self.palet_satirlar) - 1, i))
        if self.palet_satirlar[i] is None:      # grup basligi secilemez
            oteki = [j for j in adaylar if (j > i if yon > 0 else j < i)]
            i = (oteki[0] if yon > 0 else oteki[-1]) if oteki else adaylar[0]
        self.palet_secim = i
        self.palet_liste.selection_set(i)
        self.palet_liste.activate(i)
        self.palet_liste.see(i)

    def palet_gez(self, yon: int) -> None:
        adaylar = self._palet_adaylar()
        if not adaylar:
            return
        if self.palet_secim in adaylar:
            i = adaylar.index(self.palet_secim) + yon
            hedef = adaylar[max(0, min(len(adaylar) - 1, i))]
        else:
            hedef = adaylar[0]
        self.palet_sec(hedef, yon)

    def palet_secili(self) -> str | None:
        if 0 <= self.palet_secim < len(self.palet_satirlar):
            return self.palet_satirlar[self.palet_secim]
        return None

    def _palet_komuta_git(self, komut: str) -> None:
        if komut in self.palet_satirlar:
            self.palet_sec(self.palet_satirlar.index(komut), 1)

    def palet_calistir(self) -> None:
        komut = self.palet_secili()
        if komut is None:
            return
        if komut == "dil":              # palet kapanmasin: dil listesi yerinde acilir
            self.dil_menusu()
            return
        if komut == "tema":             # dil gibi: secim listesi yerinde acilir
            self.tema_menusu()
            return
        if komut == "geri-acma-siniri":
            self.sinir_menusu()
            return
        self.paleti_kapat()
        self.calistir(komut)

    def palet_fare(self, olay) -> str:
        if self.palet_kip == "liste":
            self.palet_sec(self.palet_liste.nearest(olay.y), 1)
        self.palet_girdi.focus_set()
        return "break"      # listbox odagi kapmasin, tuslar girdide kalsin

    def palet_ipucunu_tazele(self) -> None:
        kip = "eylem" if self.palet_kip in SECIM_KIPLERI else self.palet_kip
        ipucu = self.m(f"ipucu_{kip}") \
            if kip in ("liste", "eylem", "kaldir", "yakala", "onay") else ""
        self.palet_ipucu.config(text=ipucu)

    # -- palet: eylem menusu -----------------------------------------------

    def alt_menu_ac(self, baslik: str, satirlar: list[tuple[str, str]],
                    ogeler: list[str]) -> None:
        self.alt_baslik.config(text=f"[ {baslik} ]")
        self.alt_liste.delete(0, "end")
        en = max(len(a) + len(b) for a, b in satirlar) + 6
        for sol, sag in satirlar:
            self.alt_liste.insert("end", f" {sol}{sag.rjust(en - len(sol) - 2)} ")
        self.alt_liste.config(width=en, height=len(satirlar))
        self.alt_ogeleri = ogeler
        self.alt_secim = 0
        self.alt_liste.selection_clear(0, "end")
        self.alt_liste.selection_set(0)
        self.alt_menu.place(relx=1.0, rely=1.0, x=-12, y=-34, anchor="se")
        self.alt_menu.lift()
        self.palet_ipucunu_tazele()

    def alt_menuyu_kapat(self) -> None:
        self.alt_menu.place_forget()
        self.alt_ogeleri = []
        if self.palet_kip in ("eylem", "kaldir", *SECIM_KIPLERI):
            self.palet_kip = "liste"
        self.palet_ipucunu_tazele()

    def alt_gez(self, yon: int) -> None:
        if not self.alt_ogeleri:
            return
        self.alt_secim = max(0, min(len(self.alt_ogeleri) - 1, self.alt_secim + yon))
        self.alt_liste.selection_clear(0, "end")
        self.alt_liste.selection_set(self.alt_secim)
        self.alt_liste.see(self.alt_secim)

    def alt_fare(self, olay) -> str:
        i = self.alt_liste.nearest(olay.y)
        if 0 <= i < len(self.alt_ogeleri):
            self.alt_secim = i
            self.alt_liste.selection_clear(0, "end")
            self.alt_liste.selection_set(i)
        self.palet_girdi.focus_set()
        return "break"

    def eylem_menusu(self) -> None:
        komut = self.palet_secili()
        if komut is None:
            return
        self.palet_hedef = komut
        tuslar = self.komut_tuslari().get(komut, [])
        satirlar = [(self.m("secenek_calistir"), "enter"), (self.m("secenek_tus_ata"), "^K")]
        ogeler = ["calistir", "tus-ata"]
        if tuslar:
            satirlar.append((self.m("secenek_tus_kaldir"), ""))
            ogeler.append("tus-kaldir")
        if sorted(tuslar) != sorted(self.varsayilan_tuslar(komut)):
            satirlar.append((self.m("secenek_varsayilan"), ""))
            ogeler.append("varsayilan")
        self.palet_kip = "eylem"
        self.alt_menu_ac(self.m("eylemler_baslik", komut=self.ad(komut)), satirlar, ogeler)

    def dil_menusu(self) -> None:
        """Dil secim listesi: [x] English / [ ] Türkçe / [ ] Deutsch.

        Palet kapaliysa (`:lang`, tusa baglanmis `dil`) once acilir. Secim
        paleti kapatmaz; liste hemen yeni dilde yeniden cizilir.
        """
        if self.mod != "palet":
            self.eylemler()
        self._palet_komuta_git("dil")
        simdiki = self.ayar["dil"]
        satirlar = [(f"[{'x' if kod == simdiki else ' '}] {ad}", kod)
                    for kod, ad in DILLER.items()]
        self.palet_kip = "dil"
        self.alt_menu_ac(self.m("dil_baslik"), satirlar, list(DILLER))
        if simdiki in DILLER:                   # imlec secili dilde baslasin
            self.alt_gez(list(DILLER).index(simdiki))

    def tema_menusu(self) -> None:
        """Tema secim listesi, dil_menusu ile ayni duzen. Her satir kendi
        temasinin vurgu renginde (menu zemininde okunuyorsa)."""
        if self.mod != "palet":
            self.eylemler()
        self._palet_komuta_git("tema")
        simdiki = self.ayar["tema"]
        dil = self.ayar["dil"]
        satirlar = [(f"[{'x' if t == simdiki else ' '}] {komut_adi(f'tema-{t}', dil)}", "")
                    for t in TEMALAR]
        self.palet_kip = "tema"
        self.alt_menu_ac(self.m("tema_baslik"), satirlar, list(TEMALAR))
        for i, t in enumerate(TEMALAR):
            renk = TEMALAR[t]["vurgu"]
            if kontrast(renk, self.ayar["panel-zemin"]) >= 3:
                self.alt_liste.itemconfig(i, foreground=renk)
        if simdiki in TEMALAR:                  # imlec secili temada baslasin
            self.alt_gez(list(TEMALAR).index(simdiki))

    def sinir_menusu(self) -> None:
        """Geri acma siniri: [x] 1 belge ... [ ] 10 belge, dil/tema gibi."""
        if self.mod != "palet":
            self.eylemler()
        self._palet_komuta_git("geri-acma-siniri")
        simdiki = self._kapanan_siniri()
        varsayilan = VARSAYILAN_AYAR["kapanan-belgeler"]
        satirlar = [(f"[{'x' if n == simdiki else ' '}] {' ' if n < 10 else ''}"
                     f"{self.m('sinir_satir', n=n)}",
                     self.m("sinir_varsayilan") if n == varsayilan else "")
                    for n in range(1, KAPANAN_EN_COK + 1)]
        self.palet_kip = "sinir"
        self.alt_menu_ac(self.m("sinir_baslik"), satirlar, list(range(1, KAPANAN_EN_COK + 1)))
        self.alt_gez(simdiki - 1)               # imlec secili degerde baslasin

    def alt_onayla(self) -> None:
        if not (0 <= self.alt_secim < len(self.alt_ogeleri)):
            return
        secim = self.alt_ogeleri[self.alt_secim]
        if self.palet_kip == "kaldir":
            self.tusu_kaldir_uygula(secim)
            return
        if self.palet_kip == "dil":
            self.alt_menuyu_kapat()
            self.dili_ayarla(secim)
            return
        if self.palet_kip == "tema":
            self.alt_menuyu_kapat()
            self.tema_uygula(secim)
            return
        if self.palet_kip == "sinir":
            self.alt_menuyu_kapat()
            self.kapanan_siniri_ayarla(secim)
            return
        if secim == "calistir":
            self.palet_calistir()
        elif secim == "tus-ata":
            self.tus_ata()
        elif secim == "tus-kaldir":
            self.tusu_kaldir()
        elif secim == "varsayilan":
            self.varsayilana_don()

    # -- palet: tus atama --------------------------------------------------

    def tus_ata(self) -> None:
        self.alt_menu.place_forget()
        self.alt_ogeleri = []
        self.palet_kip = "yakala"
        self.palet_yeni_tus = ""
        self.yakala_goster()

    def yakala_goster(self) -> None:
        komut = self.palet_hedef
        simdiki = "  ".join(self.komut_tuslari().get(komut, [])) or self.m("yok")
        if self.palet_kip == "yakala":
            self.yakala_ust.config(text=f"{self.ad(komut)}  <-  ___")
            self.yakala_orta.config(text=self.m("simdiki_tuslar", tuslar=simdiki),
                                    fg=self.ayar["sonuk"])
            self.yakala_alt.config(text=self.m("yakala_bekle"))
        else:
            self.yakala_ust.config(text=f"{self.ad(komut)}  <-  {self.palet_yeni_tus}")
            self.yakala_orta.config(text=self.atama_uyarisi(self.palet_yeni_tus),
                                    fg=self.ayar["uyari"])
            self.yakala_alt.config(text=self.m("yakala_onay"))
        self.yakala.place(relx=0.5, rely=0.5, anchor="center")
        self.yakala.lift()
        self.palet_ipucunu_tazele()

    def paleti_kilitler(self, degisim: dict[str, str | None]) -> bool:
        """Degisimden sonra paleti acan hic tus kalmiyor mu?

        Palet tus atamanin tek yolu; son tusu giderse geri getirecek bir
        ekran da kalmaz ve bu rubricrc'ye kalici yazildigi icin her acilista
        tekrarlar. Bu yuzden `eylemler`in son tusu kaldirilamaz / alinamaz.
        """
        sonra = dict(self.tuslar)
        for tus, komut in degisim.items():
            if komut is None:
                sonra.pop(tus, None)
            else:
                sonra[tus] = komut
        return "eylemler" not in {komut_kimligi(k) for k in sonra.values()}

    def atama_uyarisi(self, tus: str) -> str:
        sahip = komut_kimligi(self.tuslar[tus]) if tus in self.tuslar else None
        if sahip == self.palet_hedef:
            return self.m("zaten_bagli", tus=tus)
        if self.paleti_kilitler({tus: self.palet_hedef}):
            return self.m("kilit_uyari", tus=tus)
        if sahip:
            return self.m("catisma", tus=tus, sahip=self.ad(sahip))
        if tus.isdigit():
            return self.m("sayi_tusu")
        if tus == "g" and any(k.startswith("g") and len(k) == 2 for k in self.tuslar):
            return self.m("g_tusu")
        return ""

    def yakala_tus(self, ad: str) -> str:
        if not ad:
            return "break"              # salt Ctrl/Shift/Alt basildi, bekle
        if ad == "<Esc>":
            self.yakalamayi_bitir()
            self.bildir(self.m("atama_iptal"), "uyari")
            return "break"
        if self.palet_kip == "onay" and ad == "<Return>":
            self.tus_atamasini_uygula()
            return "break"
        self.palet_yeni_tus = ad
        self.palet_kip = "onay"
        self.yakala_goster()
        return "break"

    def yakalamayi_bitir(self) -> None:
        self.yakala.place_forget()
        self.palet_kip = "liste"
        self.palet_yeni_tus = ""
        self.palet_girdi.focus_set()
        self.palet_ipucunu_tazele()

    def tus_atamasini_uygula(self) -> None:
        tus, komut = self.palet_yeni_tus, self.palet_hedef
        if not tus or not komut:
            self.yakalamayi_bitir()
            return
        if self.paleti_kilitler({tus: komut}):
            self.bildir(self.m("kilit_kisa", tus=tus), "uyari")
            return                      # onay ekraninda kal, baska tusa basilabilir
        onceki = komut_kimligi(self.tuslar[tus]) if tus in self.tuslar else None
        self.tuslar[tus] = komut
        yazildi = self.rc_tus_yaz({tus: komut})
        self.yakalamayi_bitir()
        self.palet_doldur()
        self._palet_komuta_git(komut)
        alinan = self.m("alindi_ek", onceki=self.ad(onceki)) \
            if onceki and onceki != komut else ""
        self.bildir(f"map {tus} {komut}{alinan}{'' if yazildi else self.m('rc_yazilamadi_ek')}",
                    "vurgu" if yazildi else "hata")

    def tusu_kaldir(self) -> None:
        tuslar = self.komut_tuslari().get(self.palet_hedef, [])
        if not tuslar:
            self.bildir(self.m("bagli_tus_yok", komut=self.ad(self.palet_hedef)), "uyari")
            return
        if len(tuslar) == 1:
            self.tusu_kaldir_uygula(tuslar[0])
            return
        self.palet_kip = "kaldir"
        self.alt_menu_ac(self.m("hangi_tus", komut=self.ad(self.palet_hedef)),
                         [(t, "") for t in tuslar], tuslar)

    def tusu_kaldir_uygula(self, tus: str) -> None:
        if self.paleti_kilitler({tus: None}):
            self.alt_menuyu_kapat()
            self.bildir(self.m("kaldirilamaz", tus=tus), "uyari")
            return
        self.tuslar.pop(tus, None)
        yazildi = self.rc_tus_yaz({tus: None})
        self.alt_menuyu_kapat()
        self.palet_doldur()
        self._palet_komuta_git(self.palet_hedef)
        self.bildir(f"unmap {tus}{'' if yazildi else self.m('rc_yazilamadi_ek')}",
                    "vurgu" if yazildi else "hata")

    def varsayilana_don(self) -> None:
        komut = self.palet_hedef
        varsayilan = self.varsayilan_tuslar(komut)
        degisim: dict[str, str | None] = {}
        for tus in self.komut_tuslari().get(komut, []):
            if tus not in varsayilan:
                degisim[tus] = None
                self.tuslar.pop(tus, None)
        for tus in varsayilan:
            if komut_kimligi(self.tuslar.get(tus, "")) != komut:
                degisim[tus] = komut
                self.tuslar[tus] = komut
        if not degisim:
            self.alt_menuyu_kapat()
            return
        yazildi = self.rc_tus_yaz(degisim)
        self.alt_menuyu_kapat()
        self.palet_doldur()
        self._palet_komuta_git(komut)
        geri = "  ".join(varsayilan) or self.m("tus_yok")
        self.bildir(self.m("varsayilana_dondu", komut=self.ad(komut), tuslar=geri)
                    + ("" if yazildi else self.m("rc_yazilamadi_ek")),
                    "vurgu" if yazildi else "hata")

    # -- palet: rubricrc'ye yazma --------------------------------------------

    def rc_tus_yaz(self, degisimler: dict[str, str | None],
                   ayarlar: dict[str, str] | None = None) -> bool:
        """Tus (ve paletten degisen ayar) degisikligini rubricrc'ye kalici yazar.

        Kullanicinin elle yazdigi satirlara dokunulmaz: paletten yapilan her
        sey dosyanin sonundaki isaretli blokta toplanir ve o blok her seferinde
        bastan uretilir. Varsayilana donen bir tus blokta yer tutmaz, cikar.
        Ayarlar ise hep yazilir: blok dosyanin sonunda oldugu icin kullanicinin
        yukarida elle yazdigi `set` satirini ezer, paletteki son secim gecer.
        """
        yol = self.yapi.yol
        satirlar: list[str] = [self.m("rc_bas1"), self.m("rc_bas2"), ""]
        satir_sonu = "\n"
        if os.path.exists(yol):
            try:
                with open(yol, encoding="utf-8-sig", newline="") as f:
                    ham = f.read()
            except OSError as e:
                self.bildir(self.m("rc_okunamadi", e=e), "hata")
                return False
            satirlar = ham.splitlines()
            if "\r\n" in ham:
                satir_sonu = "\r\n"

        bas = son = None
        for i, s in enumerate(satirlar):
            if s.strip() == RC_BLOK_BAS and bas is None:
                bas = i
            elif s.strip() == RC_BLOK_SON and bas is not None and son is None:
                son = i
        blok_var = bas is not None and son is not None and son > bas

        kayit: dict[str, str | None] = {}
        ayar_kaydi: dict[str, str] = {}
        if blok_var:
            for s in satirlar[bas + 1:son]:
                p = s.split(None, 2)
                if len(p) >= 3 and p[0] == "map":
                    kayit[p[1]] = p[2].strip()
                elif len(p) == 2 and p[0] == "unmap":
                    kayit[p[1]] = None
                elif len(p) >= 3 and p[0] == "set":
                    ayar_kaydi[p[1]] = p[2].strip()
        blok_maplari = {t for t, k in kayit.items() if k is not None}
        kayit.update(degisimler)
        ayar_kaydi.update(ayarlar or {})

        govde = [f"set {a} {d}" for a, d in ayar_kaydi.items()]
        for tus, komut in kayit.items():
            if komut is None:
                # Tusu blokta biz baglamissak satiri silmek yeter. Varsayilansa
                # ya da kullanicinin kendi satirindan geliyorsa unmap sart.
                if tus in VARSAYILAN_TUSLAR or tus not in blok_maplari:
                    govde.append(f"unmap {tus}")
            elif VARSAYILAN_TUSLAR.get(tus) != komut:
                govde.append(f"map {tus} {komut}")

        blok = [RC_BLOK_BAS, self.m("rc_blok1"), self.m("rc_blok2"),
                *sorted(govde), RC_BLOK_SON]
        if blok_var:
            satirlar[bas:son + 1] = blok
        else:
            if satirlar and satirlar[-1].strip():
                satirlar.append("")
            satirlar.extend(blok)

        try:
            os.makedirs(ayar_dizini(), exist_ok=True)
            gecici = yol + ".tmp"
            with open(gecici, "w", encoding="utf-8", newline="") as f:
                f.write(satir_sonu.join(satirlar) + satir_sonu)
            os.replace(gecici, yol)
        except OSError as e:
            self.bildir(self.m("rc_yazilamadi", e=e), "hata")
            return False
        return True

    # -- palet: tus surumu -------------------------------------------------

    def palet_tus(self, olay) -> str | None:
        ad = self.tus_adini_coz(olay)
        kip = self.palet_kip

        if kip in ("yakala", "onay"):
            return self.yakala_tus(ad)

        alt_menude = kip in ("eylem", "kaldir", *SECIM_KIPLERI)

        if ad == "<Esc>":
            self.alt_menuyu_kapat() if alt_menude else self.paleti_kapat()
            return "break"
        if ad == "<C-k>":
            self.alt_menuyu_kapat() if alt_menude else self.eylem_menusu()
            return "break"
        if ad == "<Return>":
            self.alt_onayla() if alt_menude else self.palet_calistir()
            return "break"

        adim = {"<Down>": 1, "<C-n>": 1, "<Up>": -1, "<C-p>": -1,
                "<Next>": 8, "<Prior>": -8}.get(ad)
        if alt_menude and adim is None:
            adim = {"j": 1, "k": -1}.get(ad)
        if adim is not None:
            self.alt_gez(adim) if alt_menude else self.palet_gez(adim)
            return "break"

        if alt_menude:
            return "break"          # alt menu acikken arama satirina yazilmaz
        return None                 # harf girdiye dussun, izleyici suzsun

    # -- komut satiri ------------------------------------------------------

    def komut_modu(self, onek: str = ":") -> None:
        self.mod = "komut" if onek == ":" else "arama"
        self.arama_yonu = -1 if onek == "?" else 1
        self.komut_girdi.pack(side="bottom", fill="x", before=self.cubuk)
        self.komut_girdi.delete(0, "end")
        self.komut_girdi.insert(0, onek)
        self.komut_girdi.icursor("end")
        self.komut_girdi.focus_set()

    def komut_iptal(self) -> None:
        self.komut_girdi.pack_forget()
        self.mod = "normal"
        self.tuval.focus_set()
        self.durumu_tazele()

    def komut_onayla(self, olay=None) -> str:
        ham = self.komut_girdi.get()
        self.komut_iptal()
        if not ham:
            return "break"
        onek, govde = ham[0], ham[1:].strip()
        if onek in "/?":
            if govde:
                self.arama_yonu = -1 if onek == "?" else 1
                self.ara(govde)
        elif onek == ":":
            self.komutu_isle(govde)
        return "break"

    def komutu_isle(self, satir: str) -> None:
        if not satir:
            return
        self.gecici_ileti = ""      # onceki ileti yeni komutun ustunde kalmasin
        parca = satir.split(None, 1)
        ad = parca[0]
        arg = parca[1].strip() if len(parca) > 1 else ""

        takma = {"q": "quit", "o": "open", "e": "open", "r": "reload",
                 "nohl": "nohlsearch", "bm": "bmark"}
        ad = takma.get(ad, ad)

        if ad == "quit":
            self.cik()
        elif ad == "open":
            if arg:
                self.belgeyi_ac(arg)
            else:
                self.ac()
        elif ad == "reload":
            if self.pdf_yolu:
                yer = self.ofset()
                self.belgeyi_ac(self.pdf_yolu)
                self.ofset_ata(yer, ciz=True)
        elif ad == "set":
            p = arg.split(None, 1)
            if len(p) == 1:
                p.append("true")
            if len(p) == 2:
                if not self.yapi.ata(p[0], p[1]):
                    self.bildir(self.yapi.hata_metinleri()[-1], "hata")
                    return
                self.ayarlar_degisti()
                self.bildir(f"set {p[0]} = {self.ayar.get(p[0])}", "vurgu")
        elif ad in ("theme", "tema", "thema"):
            if arg:
                kimlik = komut_kimligi(arg)
                self.tema_uygula(kimlik[5:] if kimlik.startswith("tema-") else katla(arg))
            else:                        # tek basina: secim listesi
                self.tema_menusu()
        elif ad == "lang":
            if arg:
                self.dili_ayarla(arg)
            else:
                self.dil_menusu()       # :lang tek basina -> secim listesi
        elif ad == "map":
            p = arg.split(None, 1)
            if len(p) == 2:
                self.tuslar[p[0]] = p[1]
                self.bildir(f"map {p[0]} -> {p[1]}", "vurgu")
        elif ad == "unmap":
            self.tuslar.pop(arg, None)
        elif ad == "goto":
            try:
                self.sayfaya_git(int(arg) - 1)
            except ValueError:
                self.bildir(self.m("goto_kullanim"), "hata")
        elif ad == "zoom":
            try:
                self._bekleyen_zoomu_birak()
                self.sigdir = "yok"
                self.zoom = max(self.ayar["en-az-yakinlastirma"],
                                min(self.ayar["en-cok-yakinlastirma"], float(arg) / 100.0))
                self.yenile()
            except ValueError:
                self.bildir(self.m("zoom_kullanim"), "hata")
        elif ad == "nohlsearch":
            self.vurguyu_kapat()
        elif ad == "bmark":
            self.yer_imi_koy(arg or f"s{self.aktif_sayfa + 1}")
        elif ad == "blist":
            self.yer_imlerini_goster()
        elif ad == "bdelete":
            imler = self.kalici.dosya(self.pdf_yolu).get("yer-imleri", {})
            if imler.pop(arg, None) is not None:
                self.kalici.yaz()
                self.bildir(self.m("silindi", ad=arg), "vurgu")
        elif ad == "export":
            self.disa_aktar(arg)
        elif ad == "info":
            self.bilgi()
        elif ad == "toc":
            self.icindekiler()
        elif ad == "rotate":
            self.dondur()
        elif ad == "rc":
            self.bildir(self.yapi.yol, "vurgu")
        elif ad == "help":
            self.yardim()
        else:
            # cikplak ic komut adi da kabul: ":sonraki-sayfa"
            # her dildeki ad da olur: ":next-page", ":sonraki-sayfa", ":aşağı"
            if komut_kimligi(ad) in self.komutlar:
                self.komutlar[komut_kimligi(ad)]()
            else:
                self.bildir(self.m("bilinmeyen_komut", ad=ad), "hata")

    # -- komutlar ----------------------------------------------------------

    def _komut_tablosu(self) -> dict:
        return {
            "asagi":        lambda: self.kaydir(self.ayar["kaydirma-adimi"] * self.sayi(1)),
            "yukari":       lambda: self.kaydir(-self.ayar["kaydirma-adimi"] * self.sayi(1)),
            "sola":         lambda: self.yatay_kaydir(-self.sayi(1)),
            "saga":         lambda: self.yatay_kaydir(self.sayi(1)),
            "yarim-asagi":  lambda: self.kaydir(self.gorunur_yukseklik() / 2),
            "yarim-yukari": lambda: self.kaydir(-self.gorunur_yukseklik() / 2),
            "sayfa-ileri":  lambda: self.kaydir(self.gorunur_yukseklik() * 0.92),
            "sayfa-geri":   lambda: self.kaydir(-self.gorunur_yukseklik() * 0.92),
            "sonraki-sayfa": lambda: self.sayfaya_git(self.aktif_sayfa + self.sayi(1), zipla=False),
            "onceki-sayfa": lambda: self.sayfaya_git(self.aktif_sayfa - self.sayi(1), zipla=False),
            "ilk-sayfa":    lambda: self.sayfaya_git(0),
            "son-sayfa":    self.son_sayfa,
            "yakinlastir":  lambda: self.yakinlastir(1),
            "uzaklastir":   lambda: self.yakinlastir(-1),
            "sigdir-genislik": lambda: self.sigdirma_kipi("genislik"),
            "sigdir-sayfa": lambda: self.sigdirma_kipi("sayfa"),
            "yakinlastirma-sifirla": self.yakinlastirmayi_sifirla,
            "dondur":       self.dondur,
            "ters-renk":    self.ters_renk,
            "cift-sayfa":   self.cift_sayfa,
            "icindekiler":  self.icindekiler,
            "eylemler":     self.eylemler,
            "tam-ekran":    self.tam_ekran,
            "sunum":        self.sunum,
            "durum-cubugu": self.durum_cubugu_gizle,
            "baslik-cubugu": self.baslik_cubugu_degistir,
            "dil":          self.dil_menusu,
            "vurgu-kalemi": self.vurgu_kalemi,
            "vurgular":     self.vurgu_listesi,
            "vurgu-geri-al": self.vurgu_geri_al,
            "vurgulari-aktar": self.vurgulari_aktar,
            "ara-ileri":    lambda: self.komut_modu("/"),
            "ara-geri":     lambda: self.komut_modu("?"),
            "sonraki-bulgu": lambda: self.bulguya_git(self.arama_yonu),
            "onceki-bulgu": lambda: self.bulguya_git(-self.arama_yonu),
            "vurguyu-kapat": self.vurguyu_kapat,
            "komut-modu":   lambda: self.komut_modu(":"),
            "cik":          self.cik,
            "geri-zipla":   lambda: self.zipla(-1),
            "ileri-zipla":  lambda: self.zipla(1),
            "yeniden-yukle": lambda: self.komutu_isle("reload"),
            "ac":           self.ac,
            "sonraki-belge": lambda: self.belge_gez(1),
            "onceki-belge": lambda: self.belge_gez(-1),
            "belgeyi-kapat": self.belgeyi_kapat,
            "kapanani-ac":  self.kapanani_ac,
            "geri-acma-siniri": self.sinir_menusu,
            "belgeler":     self.belge_listesi,
            "tema":         self.tema_menusu,
            **{f"tema-{t}": (lambda t=t: self.tema_uygula(t)) for t in TEMALAR},
            "isaret-koy":   lambda: self.bekle("isaret-koy"),
            "isarete-git":  lambda: self.bekle("isarete-git"),
        }

    def sayi(self, varsayilan: int = 1) -> int:
        """Bekleyen sayi onekini tuketir (5j, 42G gibi)."""
        if self.sayac:
            try:
                d = int(self.sayac)
            except ValueError:
                d = varsayilan
            self.sayac = ""
            return max(1, d)
        return varsayilan

    def son_sayfa(self) -> None:
        if not self.belge:
            return
        if self.sayac:                      # 42G -> 42. sayfa
            self.sayfaya_git(self.sayi(1) - 1)
        else:
            self.sayfaya_git(self.belge.page_count - 1)

    def yakinlastir(self, yon: int, ekran: tuple[float, float] | None = None,
                    oran: float = 1.0) -> None:
        """Hedef zoom'u degistirir; cizim bosta tek sefer yapilir.

        Her olayda hemen yeniden cizmek (adim ~100-250 ms) hizli cevrilen
        tekerlegin olaylarini kuyrukta biriktiriyordu: gorunti elden geriden
        geliyordu. Artik olay yalnizca hedefi gunceller; kuyruk bosalinca
        (after_idle) birikenlerin hepsi tek cizimde uygulanir.

        `ekran`: tuval uzerinde sabit kalacak nokta (tekerlekte imlec, tusta
        ortasi). `oran`: kac adim - hassas tekerlek / dokunmatik yuzey
        120'den kucuk delta yollar, adim ona gore kesirli olur.
        """
        if not self.belge:
            return
        adim = self.ayar["yakinlastirma-adimi"] ** (oran * self.sayi(1))
        hedef = (self._hedef_zoom or self.zoom) * (adim if yon > 0 else 1 / adim)
        self._hedef_zoom = max(self.ayar["en-az-yakinlastirma"],
                               min(self.ayar["en-cok-yakinlastirma"], hedef))
        self.sigdir = "yok"
        self._zoom_ekran = ekran or (self.tuval.winfo_width() / 2,
                                     self.tuval.winfo_height() / 2)
        if self._zoom_isi is None:
            self._zoom_isi = self.after_idle(self._zoomu_uygula)

    def _zoomu_uygula(self) -> None:
        self._zoom_isi = None
        hedef, self._hedef_zoom = self._hedef_zoom, None
        if not self.belge or hedef is None:
            return
        sx, sy = self._zoom_ekran
        capa = self._capa_al(sx, sy)            # eski duzende, imlecin altindaki yer
        self.zoom = hedef
        self.tuval.delete("all")
        self.tuval_ogeleri.clear()
        self.duzeni_hesapla()
        self._capaya_don(capa, sx, sy)
        # Once yalnizca gorunen sayfalar; komsular zoom durulunca islenir.
        self.ciz(pay=0)
        if self._komsu_isi is not None:
            self.after_cancel(self._komsu_isi)
        self._komsu_isi = self.after(150, self._komsulari_ciz)

    def _komsulari_ciz(self) -> None:
        self._komsu_isi = None
        self.ciz()

    def _bekleyen_zoomu_birak(self) -> None:
        """Zoom'u dogrudan atayan komutlar (:zoom, sigdir, %100) bekleyen
        tekerlek adimini iptal eder; yoksa bosta gelip onlarin ustune yazar."""
        if self._zoom_isi is not None:
            self.after_cancel(self._zoom_isi)
            self._zoom_isi = None
        self._hedef_zoom = None

    def _capa_al(self, sx: float, sy: float) -> tuple[int, float, float] | None:
        """Tuvaldeki (sx, sy) noktasinin altindaki sayfa ve sayfa icindeki
        orani. Nokta sayfa arasindaysa en yakin sayfaya gore (oran 0-1 disi)."""
        if not self.satirlar:
            return None
        x, y = self.tuval.canvasx(sx), self.tuval.canvasy(sy)

        def uzaklik(bas: float, boy: float, v: float) -> float:
            return max(bas - v, 0.0, v - bas - boy)

        satir = min(self.satirlar, key=lambda s: uzaklik(s["y"], s["h"], y))
        s = min(satir["sayfalar"], key=lambda p: uzaklik(p["x"], p["w"], x))
        return s["no"], (x - s["x"]) / max(1, s["w"]), (y - s["y"]) / max(1, s["h"])

    def _capaya_don(self, capa: tuple[int, float, float] | None, sx: float, sy: float) -> None:
        """Yeni duzende capanin noktasini yine ekranin (sx, sy) yerine getirir."""
        if capa is None:
            return
        no, fx, fy = capa
        s = self.sayfa_yeri(no)
        if not s:
            return
        self.ofset_ata(s["y"] + fy * s["h"] - sy)
        sol = s["x"] + fx * s["w"] - sx
        self.tuval.xview_moveto(max(0.0, sol) / max(1.0, self.toplam_genislik))

    def sigdirma_kipi(self, kip: str) -> None:
        self._bekleyen_zoomu_birak()
        self.sigdir = kip
        self.yenile()

    def yakinlastirmayi_sifirla(self) -> None:
        self._bekleyen_zoomu_birak()
        self.sigdir = "yok"
        self.zoom = 1.0
        self.yenile()

    def dondur(self) -> None:
        self.donme = (self.donme + 90) % 360
        self.yenile()

    def ters_renk(self) -> None:
        self.ters = not self.ters
        self.yenile()
        self.bildir(self.m("ters_renk_durum", durum=self.m("acik" if self.ters else "kapali")),
                    "vurgu")

    def cift_sayfa(self) -> None:
        self.sutunlar = 1 if self.sutunlar > 1 else 2
        self.yenile()
        self.bildir(self.m("sutun_n", n=self.sutunlar), "vurgu")

    def tam_ekran(self) -> None:
        tam = not self.attributes("-fullscreen")
        self.attributes("-fullscreen", tam)
        self._ust_bari_yerlestir()
        if not tam:
            self.after_idle(self.cerceveyi_uygula)  # Tk cikista basligi geri koyar

    def sunum(self) -> None:
        tam = not self.attributes("-fullscreen")
        self.attributes("-fullscreen", tam)
        self.sigdir = "sayfa" if tam else "genislik"
        if tam:
            self.cubuk.pack_forget()
        else:
            self.cubuk.pack(side="bottom", fill="x")
            self.after_idle(self.cerceveyi_uygula)
        self._ust_bari_yerlestir()
        self.after(60, self.yenile)

    def durum_cubugu_gizle(self) -> None:
        if self.cubuk.winfo_ismapped():
            self.cubuk.pack_forget()
        else:
            self.cubuk.pack(side="bottom", fill="x")

    # -- pencere cercevesi (yalnizca Windows) ------------------------------
    #
    # Windows'un beyaz baslik cubugu yalnizca bu pencereden kaldirilir;
    # sistemin geneline dokunulmaz. WS_CAPTION silinir ama WS_THICKFRAME kalir:
    # gorev cubugu, Alt+Tab, Win+ok ile yaslama ve kenardan boyutlandirma
    # calismaya devam eder. Windows'un ust kenara biraktigi 6-7 px'lik koyu
    # bant WM_NCCALCSIZE'da istemci alanina geri verilerek siliniyor; ust
    # kenardan boyutlandirmayi bunun yerine temali ust bar ustleniyor.

    def baslik_cubugu_degistir(self) -> None:
        acik = not self.ayar["baslik-cubugu"]
        self.ayar["baslik-cubugu"] = acik
        self._ust_bari_yerlestir()
        yazildi = self.rc_tus_yaz({}, ayarlar={"baslik-cubugu": "true" if acik else "false"})
        self.bildir(self.m("ust_bar_durum", durum=self.m("acik" if acik else "kapali"))
                    + ("" if yazildi else self.m("rc_yazilamadi_ek")),
                    "vurgu" if yazildi else "hata")

    def cerceveyi_uygula(self) -> None:
        if sys.platform != "win32" or self.attributes("-fullscreen"):
            return
        try:
            _pencere_cercevesi(self, gizle=not self.ayar["windows-basligi"])
        except Exception as e:          # Win32 cagrisi basarisizsa rubric yine acilsin
            self.bildir(self.m("pencere_cercevesi", e=e), "hata")

    def _pencere_mesaji(self, isabet: int, olay=None) -> str | None:
        """Windows'a 'fare su kenara basildi' der; tasima/boyutlandirma
        dongusunu (yaslama dahil) Windows kendisi yurutur.

        PostMessage olmali, SendMessage DEGIL: SendMessage tasima bitene kadar
        donmez ve o modal dongu Tk olaylarini bu Python geri cagrisinin
        icinden isletir; tkinter'in ic ice geri cagrisi GIL'siz kalir ve
        surec "PyEval_RestoreThread" ile olur (pythonw'da sessizce kapanir).
        Post edilince dongu bu fonksiyon dondukten sonra, Tk'nin normal olay
        dongusunde baslar. testler\\fare.py bunu gercek fareyle dogrular.
        """
        if sys.platform != "win32" or self.attributes("-fullscreen"):
            return None
        u32 = _win32()[0]
        # Baslangic noktasi basis ani: uygulama mesgulse ve tik gec islenirse
        # imlec coktan yurumus olur; o anki yeri alirsak pencere hic kipirdamaz.
        nokta = wt.POINT()
        if olay is not None:
            nokta.x, nokta.y = olay.x_root, olay.y_root
        else:
            u32.GetCursorPos(ctypes.byref(nokta))
        u32.ReleaseCapture()
        u32.PostMessageW(wt.HWND(int(self.wm_frame(), 16)), 0x00A1, isabet,  # WM_NCLBUTTONDOWN
                         ((nokta.y & 0xFFFF) << 16) | (nokta.x & 0xFFFF))
        return "break"

    def pencereyi_tasi(self, olay=None) -> str | None:
        return self._pencere_mesaji(2, olay)                            # HTCAPTION

    def buyut_kucult(self, olay=None) -> str:
        self.state("normal" if self.state() == "zoomed" else "zoomed")
        self.update_idletasks()
        self.ust_dugmeler["buyut"].config(text="[=]" if self.state() == "zoomed" else "[+]")
        return "break"

    # -- ust bar -----------------------------------------------------------

    def _ust_bari_yerlestir(self) -> None:
        gorunsun = self.ayar["baslik-cubugu"] and not self.attributes("-fullscreen")
        if gorunsun and not self.ust_bar.winfo_ismapped():
            self.ust_bar.pack(side="top", fill="x", before=self.tuval)
        elif not gorunsun and self.ust_bar.winfo_ismapped():
            self.ust_bar.pack_forget()

    def _ust_bari_bicimle(self) -> None:
        yt = (self.ayar["yazitipi"], self.ayar["yazitipi-boy"])
        zemin = self.ayar["cubuk-zemin"]
        self.ust_bar.config(bg=zemin)
        self.ust_cizgi.config(bg=self.ayar["palet-cerceve"])
        self.ust_istem.config(bg=zemin, fg=self.ayar["vurgu"], font=yt)
        self.ust_ad.config(bg=zemin, fg=self.ayar["cubuk-on"], font=yt)
        for d in self.ust_dugmeler.values():
            d.config(bg=zemin, fg=self.ayar["sonuk"], font=yt)

    def _ust_adi_sigdir(self) -> None:
        """Uzun dosya adini ortadan kisaltir; uzanti gorunur kalsin."""
        metin = self._ust_ad_ham
        en = self.ust_bar.winfo_width() - self.ust_istem.winfo_reqwidth() - 12 \
            - sum(d.winfo_reqwidth() for d in self.ust_dugmeler.values())
        yf = tkfont.Font(font=self.ust_ad.cget("font"))
        if en > 0 and yf.measure(metin) > en:
            alt, ust = 0, len(metin)
            while alt < ust:                        # sigan en uzun kirpim
                orta = (alt + ust + 1) // 2
                sol, sag = metin[:(orta + 1) // 2], metin[len(metin) - orta // 2:]
                if yf.measure(f"{sol}...{sag}") <= en:
                    alt = orta
                else:
                    ust = orta - 1
            metin = f"{metin[:(alt + 1) // 2]}...{metin[len(metin) - alt // 2:]}" if alt else "..."
        if self.ust_ad.cget("text") != metin:
            self.ust_ad.config(text=metin)

    def _ust_kenar(self, olay) -> int | None:
        """Imlec ust kenarda mi? Windows isabet kodu (HTTOP*) ya da None."""
        if (sys.platform != "win32" or self.ayar["windows-basligi"]
                or self.state() == "zoomed" or self.attributes("-fullscreen")):
            return None
        if olay.y_root - self.winfo_rooty() > 4:
            return None
        x = olay.x_root - self.winfo_rootx()
        if x < 10:
            return 13                                                   # HTTOPLEFT
        if x > self.winfo_width() - 10:
            return 14                                                   # HTTOPRIGHT
        return 12                                                       # HTTOP

    def _ust_bar_imleci(self, olay) -> None:
        imlec = {12: "sb_v_double_arrow", 13: "size_nw_se",
                 14: "size_ne_sw"}.get(self._ust_kenar(olay), "")
        if olay.widget.cget("cursor") != imlec:
            olay.widget.config(cursor=imlec)

    def _ust_bar_basildi(self, olay) -> str | None:
        return self._pencere_mesaji(self._ust_kenar(olay) or 2, olay)

    def _dugme_uzerinde(self, ad: str, uzerinde: bool) -> None:
        renk = self.ayar["hata" if ad == "kapat" else "vurgu"] if uzerinde else self.ayar["sonuk"]
        self.ust_dugmeler[ad].config(fg=renk)

    def _dugme_tiklandi(self, olay, ad: str) -> str:
        w = olay.widget
        if 0 <= olay.x < w.winfo_width() and 0 <= olay.y < w.winfo_height():  # disarda birakildiysa vazgec
            if ad == "kapat":
                self.cik()
            elif ad == "buyut":
                self.buyut_kucult()
            elif ad == "kucult":
                self._dugme_uzerinde(ad, False)
                self.iconify()
        return "break"

    def zipla(self, yon: int) -> None:
        if yon < 0 and self.zipla_gecmis:
            self.zipla_ileri.append(self.konum_imi())
            self.konum_imine_git(self.zipla_gecmis.pop())
        elif yon > 0 and self.zipla_ileri:
            self.zipla_gecmis.append(self.konum_imi())
            self.konum_imine_git(self.zipla_ileri.pop())

    def bekle(self, ne: str) -> None:
        self.bekleyen = ne
        self.durumu_tazele()

    def ac(self) -> None:
        # Birden cok dosya secilebilir (Ctrl/Shift+tik): hepsi listeye girer,
        # sonuncusu acilir; digerleri <C-Left>/<C-Right> ile.
        yollar = filedialog.askopenfilenames(
            title=self.m("ac_baslik"),
            filetypes=[(self.m("ac_belgeler"), "*.pdf *.epub *.xps *.cbz *.mobi *.fb2"),
                       ("PDF", "*.pdf"), (self.m("ac_tumu"), "*.*")],
        )
        for yol in yollar[:-1]:
            yol = os.path.abspath(yol)
            if os.path.exists(yol):
                self.kalici.dosya(yol)["goruldu"] = time.time()
                self._listeye_ekle(yol)
        if yollar:
            self.belgeyi_ac(yollar[-1])

    def yer_imi_koy(self, ad: str) -> None:
        if not self.pdf_yolu:
            return
        kayit = self.kalici.dosya(self.pdf_yolu)
        kayit.setdefault("yer-imleri", {})[ad] = self.ofset()
        self.kalici.yaz()
        self.bildir(self.m("yer_imi", ad=ad, s=self.aktif_sayfa + 1), "vurgu")

    def yer_imlerini_goster(self) -> None:
        imler = self.kalici.dosya(self.pdf_yolu).get("yer-imleri", {})
        if not imler:
            self.bildir(self.m("yer_imi_yok"), "uyari")
            return
        self.bildir("  ".join(sorted(imler)), "vurgu")

    def disa_aktar(self, yol: str) -> None:
        if not self.belge:
            return
        yol = yol or self.m("sayfa_dosyasi", n=self.aktif_sayfa + 1)
        try:
            pix = self.belge[self.aktif_sayfa].get_pixmap(matrix=pymupdf.Matrix(2, 2))
            pix.save(yol)
            self.bildir(self.m("yazildi", yol=os.path.abspath(yol)), "vurgu")
        except Exception as e:
            self.bildir(self.m("yazilamadi", e=e), "hata")

    def bilgi(self) -> None:
        if not self.belge:
            return
        m = self.belge.metadata or {}
        self.bildir(
            f"{m.get('title') or os.path.basename(self.pdf_yolu)} | "
            f"{m.get('author') or self.m('yazar_yok')} | "
            f"{self.m('sayfa_n', n=self.belge.page_count)}",
            "vurgu",
        )

    def yardim(self) -> None:
        self.bildir(self.m("yardim"), "vurgu")

    # -- olaylar -----------------------------------------------------------

    def tus_adini_coz(self, olay) -> str:
        """Olayi `j`, `<C-d>`, `<C-S-k>`, `<A-Left>` gibi tek bir ada cevirir.

        Degistirici bitleri Windows'ta olculdu: Shift 0x1, Ctrl 0x4,
        Alt 0x20000. AltGr kendini Ctrl+Alt diye gosterir; harf uretiyorsa
        bileske degil, dogrudan o harftir (Turkce klavyede onemli).
        """
        ks = olay.keysym
        if ks in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L",
                  "Alt_R", "Win_L", "Win_R"):
            return ""
        if ks == "??" and not olay.char:
            # Unicode paketiyle gelen girdide (ekran klavyesi, AutoHotkey)
            # Tk karakterden sonra bir de bos '??' olayi uretir; sayilmasin,
            # yoksa "5 Enter"deki 5'i siler.
            return ""
        ctrl = bool(olay.state & 0x4)
        alt = bool(olay.state & 0x20000)
        shift = bool(olay.state & 0x1)
        yazi = bool(olay.char) and olay.char.isprintable()

        if ctrl and alt and yazi:
            return olay.char                    # AltGr ile uretilen karakter
        if ctrl or alt:
            temel = ks.lower() if len(ks) == 1 else OZEL_TUSLAR.get(ks, ks)
            if temel.startswith("<"):
                temel = temel[1:-1]
            onek = ("C-" if ctrl else "") + ("A-" if alt else "") + ("S-" if shift else "")
            return f"<{onek}{temel}>"
        if ks in OZEL_TUSLAR:
            ad = OZEL_TUSLAR[ks]
            # Ozel tusta shift karakterden okunamaz, ada yazilir: <S-F5>
            return f"<S-{ad[1:-1]}>" if shift and not ad.startswith("<S-") else ad
        if yazi:
            return olay.char                    # buyuk harf shift'i zaten tasir
        return f"<{ks}>"

    def tus_geldi(self, olay) -> str | None:
        if self.focus_get() in (self.komut_girdi, self.liste, self.palet_girdi):
            return None
        ad = self.tus_adini_coz(olay)
        if not ad:
            return None
        self.gecici_ileti = ""

        # isaret bekleniyor: bir sonraki tus harf olarak alinir
        if self.bekleyen in ("isaret-koy", "isarete-git"):
            harf = olay.char
            if harf and harf.isprintable():
                if self.bekleyen == "isaret-koy":
                    self.isaretler[harf] = self.konum_imi()
                    self.bildir(self.m("isaret_kondu", harf=harf), "vurgu")
                elif harf in self.isaretler:
                    self.zipla_kaydet()
                    self.konum_imine_git(self.isaretler[harf])
                else:
                    self.bildir(self.m("isaret_yok", harf=harf), "uyari")
            self.bekleyen = None
            self.durumu_tazele()
            return "break"

        # iki tuslu diziler (gg)
        if self.bekleyen == "g":
            self.bekleyen = None
            if ("g" + ad) in self.tuslar:
                self.calistir(self.tuslar["g" + ad])
                return "break"
        if ad == "g" and any(k.startswith("g") and len(k) == 2 for k in self.tuslar):
            self.bekleyen = "g"
            self.durumu_tazele()
            return "break"

        # sayi oneki
        if ad.isdigit() and not (ad == "0" and not self.sayac):
            self.sayac += ad
            self.durumu_tazele()
            return "break"

        # sayi + Enter -> o sayfaya git (42<Return>, 42G ile ayni is)
        if ad == "<Return>" and self.sayac and ad not in self.tuslar:
            self.calistir("son-sayfa")
            return "break"

        if ad in self.tuslar:
            self.calistir(self.tuslar[ad])
            return "break"

        self.sayac = ""
        return None

    def calistir(self, komut: str) -> None:
        islev = self.komutlar.get(komut_kimligi(komut))   # rubricrc'de her dildeki ad
        if islev is None:
            # rc'de dogrudan ':' komutu da yazilabilir: map <F2> :goto 1
            self.komutu_isle(komut.lstrip(":"))
            return
        try:
            islev()
        except Exception as e:
            self.bildir(f"{komut}: {e}", "hata")
        finally:
            self.sayac = ""

    def tab_geldi(self, olay) -> str:
        self.calistir(self.tuslar.get("<Tab>", "icindekiler"))
        return "break"

    def tekerlek(self, olay) -> None:
        self.kaydir(-olay.delta / 120 * self.ayar["kaydirma-adimi"] * 2)

    def ctrl_tekerlek(self, olay) -> None:
        # imlecin altindaki yer sabit kalir; delta 120 = bir tik
        self.yakinlastir(1 if olay.delta > 0 else -1, ekran=(olay.x, olay.y),
                         oran=abs(olay.delta) / 120)

    def surukle_basla(self, olay) -> None:
        self.tuval.scan_mark(olay.x, olay.y)

    def surukle(self, olay) -> None:
        self.tuval.scan_dragto(olay.x, olay.y, gain=1)
        self.ciz()

    def pencere_degisti(self, olay) -> None:
        if olay.widget is not self:
            return
        olcu = (self.winfo_width(), self.winfo_height())
        if getattr(self, "_son_olcu", None) == olcu:
            return
        self._son_olcu = olcu
        if hasattr(self, "_boyut_isi"):
            self.after_cancel(self._boyut_isi)
        self._boyut_isi = self.after(120, self.yenile)

    def yenile(self) -> None:
        """Duzeni bastan kurar; zoom/donme/sutun/pencere degisince cagrilir."""
        if self.mod == "palet":         # palet de pencereyle birlikte genisler
            self.update_idletasks()
            self._palet_genisligini_olc()
            secili = self.palet_secili()
            self.palet_doldur()
            if secili:
                self._palet_komuta_git(secili)
        if not self.belge:
            return
        if self._zoom_isi is not None:          # bekleyen tekerlek adimi kaybolmasin
            hedef = self._hedef_zoom
            self._bekleyen_zoomu_birak()
            if hedef:
                self.zoom = hedef
        im = self.konum_imi()
        self.tuval.delete("all")
        self.tuval_ogeleri.clear()
        self.duzeni_hesapla()
        self.konum_imine_git(im, ciz=False)
        self.ciz()

    def ayarlar_degisti(self) -> None:
        self.ayar["yazitipi"] = self.yazitipi_sec(self.ayar["yazitipi"])
        self.metinleri_tazele()
        self.tuval.config(bg=self.ayar["zemin"])
        self.cubuk.config(bg=self.ayar["cubuk-zemin"])
        self.durum.config(bg=self.ayar["cubuk-zemin"], fg=self.ayar["cubuk-on"],
                          font=(self.ayar["yazitipi"], self.ayar["yazitipi-boy"]))
        self.sag_durum.config(bg=self.ayar["cubuk-zemin"], fg=self.ayar["vurgu"],
                              font=(self.ayar["yazitipi"], self.ayar["yazitipi-boy"]))
        self.komut_girdi.config(bg=self.ayar["cubuk-zemin"], fg=self.ayar["vurgu"],
                                insertbackground=self.ayar["vurgu"])
        self.panel.config(bg=self.ayar["panel-zemin"])
        self.liste.config(bg=self.ayar["panel-zemin"], fg=self.ayar["cubuk-on"],
                          selectbackground=self.ayar["panel-secili"],
                          selectforeground=self.ayar["vurgu"],
                          font=(self.ayar["yazitipi"], self.ayar["yazitipi-boy"]))
        self._paleti_bicimle()
        self._ust_bari_bicimle()
        self._ust_bari_yerlestir()
        self._ust_adi_sigdir()
        self.cerceveyi_uygula()
        self.ters = bool(self.ayar["ters-renk"])
        self.sutunlar = max(1, int(self.ayar["sutunlar"]))
        self._vurgulari_yeniden_isle()
        self.onbellek.clear()
        self.yenile()

    def _paleti_bicimle(self) -> None:
        """`:set` ile renk/yazitipi degisince palet de ayni paleti kullansin."""
        yt = (self.ayar["yazitipi"], self.ayar["yazitipi-boy"])
        yt_buyuk = (self.ayar["yazitipi"], self.ayar["yazitipi-boy"] + 3)
        zemin, panel = self.ayar["palet-zemin"], self.ayar["panel-zemin"]
        self.palet.config(bg=zemin, highlightbackground=self.ayar["palet-cerceve"])
        self.palet_ust.config(bg=zemin)
        self.palet_cizgi_ust.config(bg=self.ayar["palet-cerceve"])
        self.palet_onek.config(bg=zemin, fg=self.ayar["vurgu"], font=yt_buyuk)
        self.palet_girdi.config(bg=zemin, fg=self.ayar["cubuk-on"], font=yt_buyuk,
                                insertbackground=self.ayar["vurgu"])
        self.palet_liste.config(bg=zemin, fg=self.ayar["cubuk-on"], font=yt,
                                selectbackground=self.ayar["panel-secili"],
                                selectforeground=self.ayar["vurgu"])
        self.palet_alt.config(bg=self.ayar["cubuk-zemin"])
        self.palet_alt_sol.config(bg=self.ayar["cubuk-zemin"],
                                  fg=self.ayar["sonuk"], font=yt)
        self.palet_ipucu.config(bg=self.ayar["cubuk-zemin"],
                                fg=self.ayar["cubuk-on"], font=yt)
        self.alt_menu.config(bg=panel, highlightbackground=self.ayar["palet-cerceve"])
        self.alt_baslik.config(bg=panel, fg=self.ayar["sonuk"], font=yt)
        self.alt_liste.config(bg=panel, fg=self.ayar["cubuk-on"], font=yt,
                              selectbackground=self.ayar["panel-secili"],
                              selectforeground=self.ayar["vurgu"])
        secili = self.ayar["panel-secili"]
        self.yakala.config(bg=secili, highlightbackground=self.ayar["vurgu"])
        self.yakala_ust.config(bg=secili, fg=self.ayar["vurgu"], font=yt_buyuk)
        self.yakala_orta.config(bg=secili, font=yt)
        self.yakala_alt.config(bg=secili, fg=self.ayar["sonuk"], font=yt)

    # -- durum cubugu ------------------------------------------------------

    def bildir(self, ileti: str, renk: str = "cubuk-on") -> None:
        self.gecici_ileti = ileti
        self._ileti_rengi = self.ayar.get(renk, self.ayar["cubuk-on"])
        self.durumu_tazele()

    def durum_degerleri(self) -> dict:
        toplam = self.belge.page_count if self.belge else 0
        sayfa = self.aktif_sayfa + 1 if self.belge else 0
        mod = {"normal": "", "komut": "[:]", "arama": "[/]", "palet": "[^K]",
               "icindekiler": self.m("mod_icindekiler"),
               "vurgular": self.m("mod_vurgular"),
               "belgeler": self.m("mod_belgeler")}.get(self.mod, "")
        if self.kalem and self.mod == "normal":
            mod = self.m("mod_kalem")
        if self.bekleyen:
            mod = self.m(f"bekle_{self.bekleyen}") if self.bekleyen != "g" else "[g]"
        return {
            "mod": mod,
            "dosya": os.path.basename(self.pdf_yolu) if self.pdf_yolu else "-",
            "ad": os.path.basename(self.pdf_yolu) if self.pdf_yolu else self.m("belge_yok"),
            "yol": self.pdf_yolu or "-",
            "belgeler": f" [{self._sira() + 1}/{len(self.belgeler)}]"
                        if len(self.belgeler) > 1 and self._sira() >= 0 else "",
            "sayfa": sayfa,
            "toplam": toplam,
            "yuzde": int(100 * sayfa / toplam) if toplam else 0,
            "zoom": int(self.zoom * 100),
            "sigdir": self.m(f"sigdir_{self.sigdir}") if self.sigdir in ("genislik", "sayfa")
                      else "",
            "sutun": self.sutunlar,
            "ters": self.m("gece") if self.ters else "",
            "donme": self.donme,
            "arama": f"  /{self.son_desen} [{self.bulgu_no + 1}/{len(self.bulgular)}]"
                     if self.bulgular else "",
        }

    def durumu_tazele(self) -> None:
        d = self.durum_degerleri()
        if self.gecici_ileti:
            self.durum.config(text=self.gecici_ileti,
                              fg=getattr(self, "_ileti_rengi", self.ayar["cubuk-on"]))
        else:
            try:
                metin = self.ayar["durum-bicimi"].format_map(_Esnek(d))
            except Exception:
                metin = f"{d['ad']}  {d['sayfa']}/{d['toplam']}"
            self.durum.config(text=metin, fg=self.ayar["cubuk-on"])

        sag = self.sayac or ""
        if self.belge:
            sag = f"{sag}  {d['sayfa']}/{d['toplam']}".strip()
        self.sag_durum.config(text=sag)

        try:
            self.title(self.ayar["baslik-bicimi"].format_map(_Esnek(d)))
        except Exception:
            self.title("rubric")
        if d["ad"] != self._ust_ad_ham:          # her kaydirmada olcmesin
            self._ust_ad_ham = d["ad"]
            self._ust_adi_sigdir()

    # -- cikis -------------------------------------------------------------

    def cik(self) -> None:
        self._bekleyen_zoomu_birak()
        if self._komsu_isi is not None:
            self.after_cancel(self._komsu_isi)
            self._komsu_isi = None
        if hasattr(self, "_boyut_isi"):         # yoksa yok edilmis pencerede yenile() calisir
            self.after_cancel(self._boyut_isi)
        self.konumu_kaydet()
        self.oturumu_kaydet()                   # acilista ayni belgeler geri gelsin
        try:
            if self.belge:
                self.belge.close()
        except Exception:
            pass
        self.destroy()


class _Esnek(dict):
    """Bicim dizesinde bilinmeyen yer tutucu programi dusurmesin."""

    def __missing__(self, anahtar):
        return "{" + anahtar + "}"


_WS_CAPTION = 0x00C00000
_WS_THICKFRAME = 0x00040000
_WM_NCCALCSIZE = 0x0083
_WM_NCACTIVATE = 0x0086
_WM_SETTEXT = 0x000C
_WM_SETICON = 0x0080
_WS_VISIBLE = 0x10000000
_SWP_CERCEVE = 0x1 | 0x2 | 0x4 | 0x10 | 0x20   # NOSIZE NOMOVE NOZORDER NOACTIVATE FRAMECHANGED
_ALTSINIF_KIMLIK = 0x6F6B7572                  # "rubric"


def _win32():
    """user32/dwmapi/comctl32 imzalari; ilk cagrida bir kez kurulur."""
    if getattr(_win32, "hazir", None):
        return _win32.hazir
    u32, dwm, cc = ctypes.windll.user32, ctypes.windll.dwmapi, ctypes.windll.comctl32
    u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    u32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
    u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    u32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
    u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wt.UINT]
    u32.IsZoomed.argtypes = [wt.HWND]
    u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    u32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    dwm.DwmSetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
    altsinif = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM,
                                  wt.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
    cc.DefSubclassProc.restype = ctypes.c_ssize_t
    cc.DefSubclassProc.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    cc.SetWindowSubclass.argtypes = [wt.HWND, altsinif, ctypes.c_size_t, ctypes.c_size_t]
    cc.RemoveWindowSubclass.argtypes = [wt.HWND, altsinif, ctypes.c_size_t]

    def ust_payi_kaldir(hwnd, msg, wp, lp, _kimlik, _veri):
        # Buyutulmus pencerede varsayilan hesap dogru; orada dokunma.
        if msg == _WM_NCCALCSIZE and wp and not u32.IsZoomed(hwnd):
            dik = ctypes.cast(lp, ctypes.POINTER(wt.RECT))  # NCCALCSIZE_PARAMS.rgrc[0]
            ust = dik[0].top
            sonuc = cc.DefSubclassProc(hwnd, msg, wp, lp)
            dik[0].top = ust
            return sonuc
        # Windows ust kenari hala "cerceve" sanip bu uc mesajda eski baslik
        # alanini (6 px beyaz/gri) bizim barin USTUNE boyuyor: pencere odak
        # kaybedince, baslik metni degisince (her sayfa degisimi), ikon
        # ayarlaninca. testler\cerceve.py ust satirlari olcerek dogrular.
        if msg == _WM_NCACTIVATE:
            return cc.DefSubclassProc(hwnd, msg, wp, -1)   # -1: cerceveyi boyama
        if msg in (_WM_SETTEXT, _WM_SETICON):
            # Chromium/Firefox yolu: WS_VISIBLE kisa sure dusurulunce
            # DefWindowProc metni/ikonu kaydeder ama hicbir sey cizmez.
            stil = u32.GetWindowLongPtrW(hwnd, -16)
            if stil & _WS_VISIBLE:
                u32.SetWindowLongPtrW(hwnd, -16, stil & ~_WS_VISIBLE)
                sonuc = cc.DefSubclassProc(hwnd, msg, wp, lp)
                u32.SetWindowLongPtrW(hwnd, -16, stil)
                return sonuc
        return cc.DefSubclassProc(hwnd, msg, wp, lp)

    # Geri cagrinin referansi burada tutulur; cop toplanirsa pencere coker.
    _win32.hazir = (u32, dwm, cc, altsinif(ust_payi_kaldir))
    return _win32.hazir


def _renkref(onaltili: str) -> int:
    r, g, b = (int(onaltili.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return (b << 16) | (g << 8) | r                  # COLORREF: 0x00BBGGRR


def _pencere_cercevesi(pencere: tk.Tk, gizle: bool) -> None:
    u32, dwm, cc, altsinif = _win32()
    pencere.update_idletasks()
    hwnd = wt.HWND(int(pencere.wm_frame(), 16))

    # Koyu cerceve, duz kose, kenar cizgisi sayfa-cerceve renginde (Win11;
    # eski surumler bilmedigi ozelligi sessizce reddeder).
    for ozellik, deger in ((20, 1),                                        # koyu mod
                           (33, 1),                                        # kose yuvarlatma yok
                           (34, _renkref(pencere.ayar["sayfa-cerceve"]))):  # kenar rengi
        d = ctypes.c_int(deger)
        dwm.DwmSetWindowAttribute(hwnd, ozellik, ctypes.byref(d), ctypes.sizeof(d))

    stil = u32.GetWindowLongPtrW(hwnd, -16)                             # GWL_STYLE
    if gizle:
        stil = (stil & ~_WS_CAPTION) | _WS_THICKFRAME
        cc.SetWindowSubclass(hwnd, altsinif, _ALTSINIF_KIMLIK, 0)
    else:
        stil |= _WS_CAPTION
        cc.RemoveWindowSubclass(hwnd, altsinif, _ALTSINIF_KIMLIK)
    u32.SetWindowLongPtrW(hwnd, -16, stil)
    u32.SetWindowPos(hwnd, None, 0, 0, 0, 0, _SWP_CERCEVE)


def main() -> int:
    # Birden cok dosya verilebilir (Explorer'da coklu secip surukle): hepsi
    # listeye girer, sonuncusu acilir.
    uygulama = Rubric(sys.argv[1:] or None)
    # Ilk duzen pencere daha olculmeden kuruluyor; pencere ekrana oturunca
    # gercek genislikle bir kez daha hesapla (sigdirma dogru cikssin diye).
    uygulama.after(80, uygulama.yenile)
    uygulama.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
