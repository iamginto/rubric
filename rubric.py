# -*- coding: utf-8 -*-
"""
rubric - zathura tadinda, vim tuslu bir PDF okuyucu.

    uv run rubric.py <dosya.pdf>

Zathura'nin ana fikri burada da ayni: uygulama cikplak bir goruntuleyici,
davranisi yapilandirma dosyasi belirler. Her tus ve her ayar `rubricrc`
icinden ezilebilir; ic komutlar isimleriyle disariya acik.
"""

from __future__ import annotations

# Burada yalnizca tek-pencere devrinin gerektirdikleri: devreden kopya
# (asagida) bunlarla isini bitirip cikar, digerlerini hic yuklemez.
import ctypes
import ctypes.wintypes as wt
import os
import sys

# ---------------------------------------------------------------------------
# Tek pencere: ikinci kopya dosyayi calisan rubric'e verir ve cikar
# ---------------------------------------------------------------------------
#
# "Birlikte ac" ile her PDF'te yeni bir surec acilirsa acilisin bedeli her
# seferinde bastan odeniyor: pymupdf'in ~30 MB'lik DLL'i, Tk, duzen hesabi.
# Onun yerine, calisan bir rubric varsa yollar ona WM_COPYDATA ile verilir ve
# bu surec **pymupdf'i hic import etmeden** kapanir - ikinci ve sonraki
# acilislar boylece anlik olur. Bu yuzden bu blok `import pymupdf`in ustunde:
# kazancin tamami o import'a hic girmemekten geliyor.
#
# Belge listesi zaten var (B, <C-Left/Right>), yani dosyalar tek pencerede
# birikince kaybolmuyorlar. Ayri pencereler isteyen: `set tek-pencere false`.
#
# Neden yuva (socket) degil: dinleyen bir yuva Windows Guvenlik Duvari
# penceresi actiriyor. WM_COPYDATA ayni oturumun icinde kalir, izin istemez.

IPC_SINIF = "rubric.ileti.penceresi"
_IPC_HWND_MESSAGE = -3
_IPC_WM_COPYDATA = 0x004A
_ipc_tutulan: list = []             # yordam + sinif: cop toplayici almasin


class _KOPYAVERISI(ctypes.Structure):
    """COPYDATASTRUCT"""
    _fields_ = [("dwData", ctypes.c_size_t), ("cbData", wt.DWORD),
                ("lpData", ctypes.c_void_p)]


class _PENCERE_SINIFI(ctypes.Structure):
    """WNDCLASSW"""
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE),
                ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR)]


def _ipc_penceresi() -> int:
    """Calisan rubric'in ileti penceresi; yoksa 0."""
    try:
        u32 = ctypes.windll.user32
        u32.FindWindowExW.restype = wt.HWND
        u32.FindWindowExW.argtypes = [wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR]
        return int(u32.FindWindowExW(wt.HWND(_IPC_HWND_MESSAGE), None, IPC_SINIF, None) or 0)
    except Exception:
        return 0


def _ipc_ver(hwnd: int, yollar: list[str]) -> bool:
    """Yollari calisan rubric'e gonderir. Doner: oteki aldi mi."""
    try:
        u32 = ctypes.windll.user32
        surec = wt.DWORD()
        u32.GetWindowThreadProcessId(wt.HWND(hwnd), ctypes.byref(surec))
        u32.AllowSetForegroundWindow(surec)     # oteki one gelebilsin
        veri = ("\n".join(yollar) + "\0").encode("utf-16-le")
        tampon = ctypes.create_string_buffer(veri, len(veri))
        paket = _KOPYAVERISI(1, len(veri), ctypes.cast(tampon, ctypes.c_void_p))
        u32.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, ctypes.c_void_p,
                                            wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t)]
        sonuc = ctypes.c_size_t(0)
        # SMTO_ABORTIFHUNG: oteki kilitliyse burada beklemeyip kendimiz acariz
        gonderildi = u32.SendMessageTimeoutW(wt.HWND(hwnd), _IPC_WM_COPYDATA, 0,
                                             ctypes.byref(paket), 0x0002, 4000,
                                             ctypes.byref(sonuc))
        return bool(gonderildi) and bool(sonuc.value)
    except Exception:
        return False


def _ipc_dinle(kuyruk: list) -> int:
    """Ileti penceresini kurar; gelen yollar `kuyruk`a birikir (Tk onu yoklar).

    Yordam Tk'nin ileti dongusunun icinden cagrilir (ayni is parcacigi), bu
    yuzden burada Tcl'e dokunulmuyor: yalnizca listeye eklenir.
    """
    try:
        u32 = ctypes.windll.user32
        u32.DefWindowProcW.restype = ctypes.c_ssize_t
        # argtypes sart: verilmezse ctypes lParam'i 32 bit sanip tasiyor
        u32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        yordam_turu = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT,
                                         wt.WPARAM, wt.LPARAM)

        def yordam(hwnd, ileti, wp, lp):
            if ileti != _IPC_WM_COPYDATA:
                return u32.DefWindowProcW(hwnd, ileti, wp, lp)
            try:
                paket = ctypes.cast(lp, ctypes.POINTER(_KOPYAVERISI)).contents
                metin = ctypes.wstring_at(paket.lpData, paket.cbData // 2).rstrip("\0")
                kuyruk.append([y for y in metin.split("\n") if y])
                return 1
            except Exception:
                return 0

        sinif = _PENCERE_SINIFI()
        sinif.lpfnWndProc = ctypes.cast(yordam_turu(yordam), ctypes.c_void_p)
        sinif.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        sinif.lpszClassName = IPC_SINIF
        _ipc_tutulan.append(sinif)
        u32.RegisterClassW.argtypes = [ctypes.POINTER(_PENCERE_SINIFI)]
        u32.RegisterClassW(ctypes.byref(sinif))   # zaten kayitliysa da sorun degil
        u32.CreateWindowExW.restype = wt.HWND
        u32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE,
                                        ctypes.c_void_p]
        return int(u32.CreateWindowExW(0, IPC_SINIF, "rubric", 0, 0, 0, 0, 0,
                                       wt.HWND(_IPC_HWND_MESSAGE), None,
                                       sinif.hInstance, None) or 0)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Tepsi simgesi (Ctrl-K > ayarlar > tepsi)
# ---------------------------------------------------------------------------
#
# Tepsi modunda kapatmak rubric'ten cikmaz, pencereyi gizleyip saatin yanina
# bir simge koyar: Python, Tk ve MuPDF bellekte kalir, yeniden acilis anlik.
# Simgenin mesajlarini ayri bir ileti penceresi alir; yordam yine Tk'nin
# ileti dongusunun icinden cagrildigi icin Tcl'e dokunmaz, yalnizca listeye
# yazar (bkz. _ipc_dinle) - Rubric._tepsi_yokla isler.

_TEPSI_SINIF = "rubric.tepsi.penceresi"
_TEPSI_MESAJ = 0x8000 + 1                   # WM_APP + 1
_WM_LBUTTONUP, _WM_RBUTTONUP = 0x0202, 0x0205


class _SIMGE_VERISI(ctypes.Structure):
    """NOTIFYICONDATAW"""
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT),
                ("uFlags", wt.UINT), ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON),
                ("szTip", ctypes.c_wchar * 128), ("dwState", wt.DWORD),
                ("dwStateMask", wt.DWORD), ("szInfo", ctypes.c_wchar * 256),
                ("uVersion", wt.UINT), ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", wt.DWORD), ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", wt.HICON)]


def _tepsi_simgesi(kuyruk: list, ikon_yolu: str, ipucu: str) -> tuple[int, object] | None:
    """Simgeyi ekler. Doner: (ileti penceresi, simge verisi) ya da None.
    Tiklamalar `kuyruk`a "sol" / "sag" diye duser."""
    try:
        u32 = ctypes.windll.user32
        u32.DefWindowProcW.restype = ctypes.c_ssize_t
        u32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        yordam_turu = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT,
                                         wt.WPARAM, wt.LPARAM)

        def yordam(hwnd, ileti, wp, lp):
            if ileti == _TEPSI_MESAJ:
                olay = lp & 0xFFFF
                if olay == _WM_LBUTTONUP:
                    kuyruk.append("sol")
                elif olay == _WM_RBUTTONUP:
                    kuyruk.append("sag")
                return 0
            return u32.DefWindowProcW(hwnd, ileti, wp, lp)

        sinif = _PENCERE_SINIFI()
        sinif.lpfnWndProc = ctypes.cast(yordam_turu(yordam), ctypes.c_void_p)
        sinif.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        sinif.lpszClassName = _TEPSI_SINIF
        _ipc_tutulan.append(sinif)
        u32.RegisterClassW.argtypes = [ctypes.POINTER(_PENCERE_SINIFI)]
        u32.RegisterClassW(ctypes.byref(sinif))
        u32.CreateWindowExW.restype = wt.HWND
        u32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE,
                                        ctypes.c_void_p]
        hwnd = u32.CreateWindowExW(0, _TEPSI_SINIF, "rubric", 0, 0, 0, 0, 0,
                                   wt.HWND(_IPC_HWND_MESSAGE), None, sinif.hInstance, None)
        if not hwnd:
            return None
        u32.LoadImageW.restype = wt.HANDLE
        u32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int,
                                   ctypes.c_int, wt.UINT]
        boy = u32.GetSystemMetrics(49)                      # SM_CXSMICON
        ikon = u32.LoadImageW(None, ikon_yolu, 1, boy, boy, 0x10) if ikon_yolu else None
        veri = _SIMGE_VERISI()
        veri.cbSize = ctypes.sizeof(_SIMGE_VERISI)
        veri.hWnd = hwnd
        veri.uID = 1
        veri.uFlags = 0x1 | 0x4 | (0x2 if ikon else 0)      # MESSAGE | TIP | ICON
        veri.uCallbackMessage = _TEPSI_MESAJ
        veri.hIcon = ikon
        veri.szTip = ipucu[:127]
        ctypes.windll.shell32.Shell_NotifyIconW.argtypes = [wt.DWORD,
                                                            ctypes.POINTER(_SIMGE_VERISI)]
        if not ctypes.windll.shell32.Shell_NotifyIconW(0, ctypes.byref(veri)):   # NIM_ADD
            u32.DestroyWindow(hwnd)
            return None
        return int(hwnd), veri
    except Exception:
        return None


def _tepsi_simgesini_kaldir(tepsi: tuple[int, object] | None) -> None:
    if not tepsi:
        return
    hwnd, veri = tepsi
    with contextlib.suppress(Exception):
        ctypes.windll.shell32.Shell_NotifyIconW(2, ctypes.byref(veri))      # NIM_DELETE
        if veri.hIcon:
            ctypes.windll.user32.DestroyIcon(veri.hIcon)
        ctypes.windll.user32.DestroyWindow(wt.HWND(hwnd))


def _sayfa_olcucusu(belge):
    """no -> `belge[no].rect` ile ayni boy, sayfayi yuklemeden.

    Duzen acilista her sayfanin olcusunu ister; `belge[no]` sayfayi yukleyip
    cozuyor, 1612 sayfalik kitapta 140 ms (bilgisayar yeni acildiysa dosyanin
    hepsini diskten okuyarak cok daha uzun). PDF'te CropBox'i dogrudan okumak
    + /Rotate (ust dugumden miras gelebilir; dugum basina bir kez aranir)
    ayni sonucu 31 ms'de veriyor. 126 gercek PDF + dondurulmus sentetik
    belgede birebir ayni cikti. PDF degilse ya da okunamazsa eski yol."""
    if not belge.is_pdf:
        return lambda no: belge[no].rect
    donmeler: dict[int, int] = {}

    def donme(xref: int, derinlik: int = 0) -> int:
        if xref in donmeler:
            return donmeler[xref]
        tur, deger = belge.xref_get_key(xref, "Rotate")
        if tur == "int":
            sonuc = int(deger) % 360
        else:
            tur, deger = belge.xref_get_key(xref, "Parent")
            sonuc = donme(int(deger.split()[0]), derinlik + 1)                 if tur == "xref" and derinlik < 32 else 0
        donmeler[xref] = sonuc
        return sonuc

    def olc(no: int):
        try:
            r = belge.page_cropbox(no)
            w, h = r.width, r.height
            if donme(belge.page_xref(no)) % 180:
                w, h = h, w
            return pymupdf.Rect(0, 0, w, h)
        except Exception:
            return belge[no].rect
    return olc


def _tek_pencere_ister() -> bool:
    """rubricrc'de `set tek-pencere false` yazmiyorsa evet.

    rubricrc burada elle okunuyor: Yapilandirma sinifi da varsayilanlar da
    asagida, yani pymupdf'ten sonra tanimli - oysa bu kararin pymupdf import
    edilmeden verilmesi gerekiyor, kazanc oradan geliyor.
    """
    kok = os.environ.get("APPDATA") or os.path.expanduser("~")
    try:
        with open(os.path.join(kok, "rubric", "rubricrc"), encoding="utf-8") as f:
            for satir in f:
                p = satir.split("#")[0].split()
                if len(p) >= 2 and p[0] == "set" and p[1] == "tek-pencere":
                    return (p[2] if len(p) > 2 else "true").lower() not in (
                        "0", "false", "off", "no", "hayir", "kapali", "nein", "aus")
    except OSError:
        pass
    return True


if __name__ == "__main__" and _tek_pencere_ister():
    _calisan = _ipc_penceresi()
    if _calisan and _ipc_ver(_calisan, [os.path.abspath(y) for y in sys.argv[1:]]):
        raise SystemExit(0)

import bisect                                     # noqa: E402
import collections                                # noqa: E402
import contextlib                                 # noqa: E402
import json                                       # noqa: E402
import queue                                      # noqa: E402
import re                                         # noqa: E402
import hashlib                                    # noqa: E402
import shutil                                    # noqa: E402
import subprocess                                 # noqa: E402
import threading                                  # noqa: E402
import time                                       # noqa: E402

# Devreden kopya buraya hic gelmez: tkinter (Tcl + Tk DLL'leri) ve pymupdf
# (~30 MB'lik MuPDF) yalnizca gercekten pencere acacak kopyada yuklenir.
#
# pymupdf import'u acilisin en buyuk parcasi (sicakken ~80 ms; bilgisayar yeni
# acildiysa 30 MB'lik DLL diskten okundugu icin cok daha uzun). Ayri is
# parcaciginda baslar: DLL diskten okunurken Python GIL'i birakiyor, bu arada
# ana is parcacigi Tk'yi kurup pencereyi cizer. Belge acilmadan hemen once
# _pymupdf_bekle() onu bekler; modul baska yerden import edildiyse (testler,
# tus-karti.py) en sonda beklenir, yani disaridan bakan icin fark yok.
pymupdf = None
_pymupdf_isi = threading.Thread(target=__import__, args=("pymupdf",),
                                name="pymupdf", daemon=True)
_pymupdf_isi.start()

import tkinter as tk                              # noqa: E402
from tkinter import filedialog                    # noqa: E402
from tkinter import font as tkfont                # noqa: E402


def _pymupdf_bekle() -> None:
    global pymupdf
    if pymupdf is None:
        _pymupdf_isi.join()
        import pymupdf as _modul                  # is parcacigi yuklediyse anlik
        pymupdf = _modul


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
    "ters-renk":      False,       # gece modu
    # Gece modu nasil boyar. tema: sayfa gri tonlanir, siyah yazi temanin
    # yazi rengine (cubuk-on), beyaz kagit temanin zeminine esler (zathura'nin
    # recolor'u); tema degisince sayfa da doner. ters: duz renk tersleme.
    "gece-modu":      "tema",
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
    # Yalnizca "su sayfa" diyen bir baglantida (bkz. capa_etiketleri) gidilen
    # yer bu kadar ms isaretli kalir; ayni sayfaya donen baglantida "hicbir sey
    # olmadi" sanilmasin diye. 0 = hic isaretleme.
    "capa-suresi":    1400,
    # Bolunmus gorunumde imlecin durdugu bolme etkin olur ("taban"): sag
    # belgenin uzerine gidip j'ye basan sagi kaydirir. false: bolme yalnizca
    # tikla ve <A-w> ile degisir.
    "fare-bolme":     True,
    "sigdir":         "genislik",  # acilis sigdirma: genislik | sayfa | yok
    "durum-cubugu":   True,
    # Secilen metni hangi tus hangi renge boyar (tus:renk). Ctrl-K > vurgu
    # renkleri buraya yazar.
    "vurgu-tuslari":  "y:sari g:yesil b:mavi p:pembe o:turuncu r:kirmizi m:mor",
    # Enter'in koydugu renk: VURGU_RENKLERI'nden biri. "sari" temanin
    # `vurgu-rengi`ne baglidir, otekiler sabit. Ctrl-K > vurgu renkleri > bosluk.
    "vurgu-varsayilan": "sari",
    # Acik: ikinci kez acilan bir PDF calisan rubric'e gider (bkz. dosyanin
    # basindaki "Tek pencere" notu). Kapatirsan her dosya kendi penceresinde
    # acilir - ama acilisin tam bedelini de her seferinde oder.
    "tek-pencere":    True,
    # <C-p> Windows'un yazdirma penceresini acar (yazici, sayfa araligi,
    # kopya). 2026-09-20'de "direkt bassin" denendi, kullanici 2026-09-21'de
    # asamali hale geri dondu. False: <C-p> pencere acmadan
    # `yazdirma-yazicisi`na basar.
    "yazdirma-penceresi": True,
    # yazdirma-penceresi false iken <C-p>'nin bastigi yazici. Bos ise Windows'un varsayilani kullanilir -
    # ama Windows'ta varsayilan cogu kez "Microsoft Print to PDF" oluyor ve
    # zaten PDF olan belgenin PDF'i cikiyor. Ctrl-K > yazici buraya yazar.
    "yazdirma-yazicisi": "",
    "baslik-cubugu":  True,        # rubric'in kendi (temali) ust bari
    # Tepsi modu (Ctrl-K > ayarlar > tepsi): kapatinca rubric cikmaz, saatin
    # yanindaki simgeye iner; yeniden acilis anlik. Kullanici kendisi acar,
    # varsayilan kapali. Gercekten cikmak: simgeye sag tik > cik.
    "tepsi":          False,
    "windows-basligi": False,      # Windows'un beyaz baslik cubugu

    # --- tex modu (T): bir yanda .tex kaynagi, yaninda canli PDF ---
    "tex-motoru":     "pdflatex",  # pdflatex | xelatex | lualatex (PATH'te olmali)
    "tex-yan":        "sol",       # editor hangi yanda: sol | sag
    "tex-oran":       50,          # editorun genisligi, tuval alaninin yuzdesi
    "tex-gecikme":    800,         # yazmayi birakinca kac ms sonra derlesin; 0 = yalniz Ctrl-S

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

# Palette secim listesi acan komutlarin alt menu kipleri ("renk": vurgu renkleri)
SECIM_KIPLERI = ("dil", "tema", "sinir", "renk", "yazici")

# Vurgu kalemi renkleri. "sari" temanin `vurgu-rengi`ni kullanir (tema
# degisince doner), otekiler sabit: beyaz sayfada carpma karisimiyla okunur
# kalacak kadar acik fosforlu renkler. Secimden sonra Enter'in koydugu renk
# bunlardan biri, `vurgu-varsayilan` ayari secer.
VURGU_RENKLERI: dict[str, str | None] = {
    "sari": None, "yesil": "#7cf29a", "mavi": "#7cc4ff", "pembe": "#ff8fd1",
    "turuncu": "#ffab4a", "kirmizi": "#ff7b7b", "mor": "#c9a2ff",
}
RENK_ADLARI: dict[str, dict[str, str]] = {
    "en": {"sari": "yellow", "yesil": "green", "mavi": "blue", "pembe": "pink",
           "turuncu": "orange", "kirmizi": "red", "mor": "purple"},
    "tr": {"sari": "sarı", "yesil": "yeşil", "mavi": "mavi", "pembe": "pembe",
           "turuncu": "turuncu", "kirmizi": "kırmızı", "mor": "mor"},
    "de": {"sari": "gelb", "yesil": "grün", "mavi": "blau", "pembe": "rosa",
           "turuncu": "orange", "kirmizi": "rot", "mor": "lila"},
}

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
    # Bolmeler. Alt secildi, Ctrl+Shift degil (bkz. yukarida <C-e>): ok tuslari
    # "saga at / sola at"in dogrudan karsiligi, <A-w> vim'in <C-w>'si gibi
    # bolme degistirir, <A-o> yine vim'deki gibi tek bolmeye doner.
    "<A-Right>": "bolme-saga",    "<A-Left>": "bolme-sola",
    "<A-w>": "bolme-gec",         "<A-o>": "bolme-tek",
    "v":"vurgu-kalemi",    "V": "vurgular",        "u": "vurgu-geri-al",
    # i: vim'deki "insert". Imlecin altinda not varsa onu duzenler.
    "i": "not-ekle",
    # U / <C-z>: son silineni geri getirir (not ya da vurgu); `u` yalniz
    # vurgularinki, ikisi ayri yigin. Not silmek silme kipinin isi.
    "U": "geri-getir",     "<C-z>": "geri-getir",
    # <Delete>: silme kipi - acikken tiklanan not ya da vurgu silinir.
    "<Delete>": "silme-kipi",
    # S: sayfa duzeni (kucuk resimler; tasi, sil, dondur, ayir). X: karartma
    # kalemi - x'in buyugu, "ustunu ciz". Ikisi de yeni dosyaya yazar.
    "S": "sayfa-duzeni",    "X": "karartma-kalemi",
    # T: tex modu (kapaliysa acar, aciksa editore gecer). <C-c>: Shift+surukle
    # ile secilen metni panoya koyar; `y` renk tusu oldugu icin yank degil.
    "T": "tex-modu",        "<C-c>": "kopyala",
    "M": "yer-imi-koy",     "b": "yer-imleri",
    # <C-S-p> degil: birden cok klavye dili kuruluyken Windows Ctrl+Shift'i
    # dil degistirmeye ayirabiliyor (bkz. yukarida <C-e>).
    "<C-p>": "yazdir",      "P": "yazdir-sec",      "<C-l>": "baglantilar",
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
        "ters-renk":      "night mode: recolor pages to the theme",

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

        "vurgu-kalemi":   "highlighter: drag, then Enter or a colour key (Shift+drag always)",
        "vurgular":       "highlight list - Enter go, x delete",
        "vurgu-geri-al":  "undo the last highlight add / delete",
        "vurgulari-aktar": "embed highlights and notes as PDF comments (<name>-highlighted.pdf, original untouched)",
        "not-ekle":       "note at the cursor: hover to read it, i to edit, empty text deletes",
        "geri-getir":     "bring back the last thing you deleted (note or highlight)",
        "silme-kipi":     "delete mode: click a note or highlight to remove it, Esc leaves",
        "sayfa-duzeni":   "organize pages: move, delete, rotate, extract - w writes a new file",
        "birlestir":      "merge: append chosen PDFs to this one (<name>-merged.pdf)",
        "karartma-kalemi": "redact pen: drag a box or click a word, Enter writes the redacted copy",
        "karartmayi-uygula": "write the redacted copy now (<name>-redacted.pdf, text really removed)",
        "ustveri-temizle": "strip metadata: author, software, dates, XMP (<name>-clean.pdf)",
        "kopyala":        "copy the selected text (shift+drag) to the clipboard",
        "tex-modu":       "tex mode: .tex source beside its live PDF (again: focus the editor)",
        "tex-derle":      "save and compile the .tex now",
        "tex-kapat":      "close tex mode (the source is saved)",

        "ac":             "pick a file and open it",
        "yeniden-yukle":  "reload the document from disk",
        "komut-modu":     "open the command line",
        "cik":            "quit rubric (documents and positions are saved)",
        "sonraki-belge":  "next document in the list (newer)",
        "onceki-belge":   "previous document in the list (older)",
        "belgeyi-kapat":  "close this document, go to its neighbour (Q quits)",
        "kapanani-ac":    "reopen the last closed document where it was, same spot in the list",
        "bolme-saga":     "throw this document to the RIGHT pane",
        "bolme-sola":     "throw this document to the LEFT pane",
        "bolme-gec":      "switch to the other pane",
        "bolme-tek":      "back to one pane (the lists merge)",
        "geri-acma-siniri": "how many closed documents can be reopened: 1-10 (persistent)",
        "yazici":         "printer for direct printing when yazdirma-penceresi is false (persistent)",
        "tepsi":          "tray mode: closing hides rubric next to the clock, reopening is instant (persistent)",
        "belgeler":       "open documents - Enter go, x close",
        "tema":           "colour theme: pick from a list (persistent)",
        "vurgu-renkleri": "highlight colours: which key paints a selection which colour (persistent)",
        "yer-imi-koy":    "bookmark this spot (named after its section)",
        "yer-imleri":     "bookmarks - Enter go, x delete, a add",
        "yazdir":         "print via the printer dialog (press again to cancel)",
        "yazdir-sec":     "print: pick a printer and pages (press again while printing to cancel)",
        "baglantilar":    "show / hide the links on the page",
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
        "ters-renk":      "gece modu: sayfayı temanın renklerine boya",

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

        "vurgu-kalemi":   "vurgu kalemi: sürükle seç, sonra Enter ya da renk tuşu (Shift+sürükle her zaman)",
        "vurgular":       "vurgu listesi - Enter git, x sil",
        "vurgu-geri-al":  "son vurgu ekleme / silmesini geri al",
        "vurgulari-aktar": "vurgu ve notları PDF yorumu olarak göm (<ad>-vurgulu.pdf, aslı değişmez)",
        "not-ekle":       "imlecin oldugu yere not: üstüne gelince okunur, i düzenler, boş metin siler",
        "geri-getir":     "en son sildiğin şeyi geri getir (not ya da vurgu)",
        "silme-kipi":     "silme kipi: tıkladığın notu ya da vurguyu siler, Esc çıkar",
        "sayfa-duzeni":   "sayfa düzeni: taşı, sil, döndür, ayır - w yeni dosyaya yazar",
        "birlestir":      "birleştir: seçtiğin PDF'leri bunun arkasına ekle (<ad>-birlesik.pdf)",
        "karartma-kalemi": "karartma kalemi: kutu sürükle ya da kelimeye tıkla, Enter karartılmış kopyayı yazar",
        "karartmayi-uygula": "karartılmış kopyayı şimdi yaz (<ad>-karartilmis.pdf, metin gerçekten silinir)",
        "ustveri-temizle": "üstverileri sil: yazar, program, tarihler, XMP (<ad>-temiz.pdf)",
        "kopyala":        "seçili metni (shift+sürükle) panoya kopyala",
        "tex-modu":       "tex modu: .tex kaynağı yanında canlı PDF (yine basınca: editöre geç)",
        "tex-derle":      ".tex'i kaydet ve şimdi derle",
        "tex-kapat":      "tex modunu kapat (kaynak kaydedilir)",

        "ac":             "dosya seçip aç",
        "yeniden-yukle":  "belgeyi diskten yeniden oku",
        "komut-modu":     "komut satırını aç",
        "cik":            "rubric'ten çık (belgeler ve konumlar kaydedilir)",
        "sonraki-belge":  "listedeki sonraki belge (daha yeni)",
        "onceki-belge":   "listedeki önceki belge (daha eski)",
        "belgeyi-kapat":  "bu belgeyi kapat, komşusuna geç (Q çıkar)",
        "kapanani-ac":    "son kapatılan belgeyi kaldığı yerden, listedeki yerine geri aç",
        "bolme-saga":     "belgeyi SAĞ bölmeye at",
        "bolme-sola":     "belgeyi SOL bölmeye at",
        "bolme-gec":      "öteki bölmeye geç",
        "bolme-tek":      "tek bölmeye dön (listeler birleşir)",
        "geri-acma-siniri": "kapatılan kaç belge geri açılabilsin: 1-10 (kalıcı)",
        "yazici":         "yazıcı: yazdirma-penceresi false iken doğrudan hangisine basılsın (kalıcı)",
        "tepsi":          "tepsi modu: kapatınca saatin yanına iner, yeniden açılış anlık (kalıcı)",
        "belgeler":       "açık belgeler - Enter git, x kapat",
        "tema":           "renk teması: listeden seç (kalıcı)",
        "vurgu-renkleri": "vurgu renkleri: hangi tuş seçimi hangi renge boyar (kalıcı)",
        "yer-imi-koy":    "buraya yer imi koy (adı bulunduğu bölümden)",
        "yer-imleri":     "yer imleri - Enter git, x sil, a ekle",
        "yazdir":         "yazdır: yazıcı penceresini aç (yazdırırken tekrar basınca iptal)",
        "yazdir-sec":     "yazdır: yazıcı ve sayfa seç (yazdırırken tekrar basınca iptal)",
        "baglantilar":    "sayfadaki bağlantıları göster / gizle",
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
        "ters-renk":      "Nachtmodus: Seiten in Themenfarben umfärben",

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

        "vurgu-kalemi":   "Textmarker: ziehen wählt, dann Enter oder Farbtaste (Shift+Ziehen immer)",
        "vurgular":       "Markierungsliste - Enter springen, x löschen",
        "vurgu-geri-al":  "letztes Markieren / Löschen rückgängig machen",
        "vurgulari-aktar": "Markierungen und Notizen als PDF-Kommentare einbetten (<Name>-markiert.pdf, Original bleibt)",
        "not-ekle":       "Notiz an der Zeigerposition: zum Lesen darauf zeigen, i bearbeitet, leer löscht",
        "geri-getir":     "zuletzt Gelöschtes zurückholen (Notiz oder Markierung)",
        "silme-kipi":     "Löschmodus: Klick entfernt Notiz oder Markierung, Esc beendet",
        "sayfa-duzeni":   "Seiten ordnen: verschieben, löschen, drehen, herauslösen - w schreibt neue Datei",
        "birlestir":      "zusammenfügen: gewählte PDFs hinten anhängen (<Name>-zusammen.pdf)",
        "karartma-kalemi": "Schwärzstift: Rahmen ziehen oder Wort klicken, Enter schreibt die geschwärzte Kopie",
        "karartmayi-uygula": "geschwärzte Kopie jetzt schreiben (<Name>-geschwaerzt.pdf, Text wirklich entfernt)",
        "ustveri-temizle": "Metadaten entfernen: Autor, Programm, Daten, XMP (<Name>-bereinigt.pdf)",
        "kopyala":        "markierten Text (Shift+Ziehen) in die Zwischenablage kopieren",
        "tex-modu":       "TeX-Modus: .tex-Quelltext neben dem Live-PDF (nochmal: zum Editor)",
        "tex-derle":      ".tex speichern und jetzt kompilieren",
        "tex-kapat":      "TeX-Modus schließen (Quelltext wird gespeichert)",

        "ac":             "Datei auswählen und öffnen",
        "yeniden-yukle":  "Dokument neu von der Festplatte laden",
        "komut-modu":     "Befehlszeile öffnen",
        "cik":            "rubric beenden (Dokumente und Positionen bleiben)",
        "sonraki-belge":  "nächstes Dokument der Liste (neuer)",
        "onceki-belge":   "voriges Dokument der Liste (älter)",
        "belgeyi-kapat":  "dieses Dokument schließen, zum Nachbarn (Q beendet)",
        "kapanani-ac":    "zuletzt geschlossenes Dokument an alter Stelle wieder öffnen",
        "bolme-saga":     "Dokument nach RECHTS werfen",
        "bolme-sola":     "Dokument nach LINKS werfen",
        "bolme-gec":      "zum anderen Bereich wechseln",
        "bolme-tek":      "zurück zu einem Bereich (Listen vereint)",
        "geri-acma-siniri": "wie viele geschlossene Dokumente wieder öffnen: 1-10 (dauerhaft)",
        "yazici":         "Drucker für direktes Drucken bei yazdirma-penceresi false (dauerhaft)",
        "tepsi":          "Tray-Modus: Schließen legt rubric neben die Uhr, erneutes Öffnen sofort (dauerhaft)",
        "belgeler":       "offene Dokumente - Enter öffnen, x schließen",
        "tema":           "Farbthema: aus einer Liste wählen (dauerhaft)",
        "vurgu-renkleri": "Markerfarben: welche Taste eine Auswahl in welcher Farbe markiert (dauerhaft)",
        "yer-imi-koy":    "Lesezeichen hier setzen (nach dem Abschnitt benannt)",
        "yer-imleri":     "Lesezeichen - Enter springen, x löschen, a hinzufügen",
        "yazdir":         "über den Druckdialog drucken (erneut drücken: abbrechen)",
        "yazdir-sec":     "drucken: Drucker und Seiten wählen (erneut drücken: abbrechen)",
        "baglantilar":    "Links auf der Seite zeigen / verbergen",
    },
}

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
               "baslik-cubugu", "baglantilar", "dil"]),
    ("arama", ["ara-ileri", "ara-geri", "sonraki-bulgu", "onceki-bulgu",
               "vurguyu-kapat"]),
    ("isaret ve ziplama", ["isaret-koy", "isarete-git", "yer-imi-koy", "yer-imleri",
                           "geri-zipla", "ileri-zipla"]),
    ("vurgu", ["vurgu-kalemi", "vurgular", "vurgu-geri-al", "vurgulari-aktar",
               "not-ekle", "geri-getir", "silme-kipi", "kopyala"]),
    ("dosya", ["ac", "belgeler", "sonraki-belge", "onceki-belge", "belgeyi-kapat",
               "kapanani-ac", "yeniden-yukle", "yazdir", "yazdir-sec", "komut-modu",
               "cik"]),
    ("pdf araclari", ["sayfa-duzeni", "birlestir", "karartma-kalemi",
                      "karartmayi-uygula", "ustveri-temizle"]),
    ("tex", ["tex-modu", "tex-derle", "tex-kapat"]),
    ("bolmeler", ["bolme-saga", "bolme-sola", "bolme-gec", "bolme-tek"]),
    ("ayarlar", ["geri-acma-siniri", "yazici", "tepsi"]),
    # Temalar gibi: palette tek satir, Enter renk listesini acar; tusu yok.
    ("vurgu renkleri", ["vurgu-renkleri"]),
    # Palette tek satir, en altta: Enter secim listesini acar (dil gibi). tema-<ad>
    # komutlari gruplarda yok, palette gorunmez; :neon, map x tema-buz icin durur.
    ("temalar", ["tema"]),
]

GRUP_ADLARI: dict[str, dict[str, str]] = {
    "en": {"gezinme": "navigation", "yakinlastirma ve duzen": "zoom and layout",
           "ekran": "display", "arama": "search", "isaret ve ziplama": "marks and jumps",
           "vurgu": "highlights", "dosya": "file", "ayarlar": "settings", "temalar": "themes", "bolmeler": "panes",
           "pdf araclari": "pdf tools", "tex": "tex",
           "vurgu renkleri": "highlight colours"},
    "tr": {"gezinme": "gezinme", "yakinlastirma ve duzen": "yakınlaştırma ve düzen",
           "ekran": "ekran", "arama": "arama", "isaret ve ziplama": "işaret ve zıplama",
           "vurgu": "vurgu", "dosya": "dosya", "ayarlar": "ayarlar", "temalar": "temalar",
           "bolmeler": "bölmeler", "pdf araclari": "pdf araçları", "tex": "tex",
           "vurgu renkleri": "vurgu renkleri"},
    "de": {"gezinme": "Navigation", "yakinlastirma ve duzen": "Zoom und Layout",
           "ekran": "Anzeige", "arama": "Suche", "isaret ve ziplama": "Marken und Sprünge",
           "vurgu": "Markierungen", "dosya": "Datei", "ayarlar": "Einstellungen",
           "temalar": "Themen", "vurgu renkleri": "Markerfarben", "bolmeler": "Bereiche",
           "pdf araclari": "PDF-Werkzeuge", "tex": "TeX"},
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
        "not_eklendi":      "note added",
        "not_guncellendi":  "note updated",
        "not_silindi":      "note deleted",
        "not_sayfa_disi":   "point the cursor at a page first",
        "not_istem":        "note>",
        "not_geri_alindi":  "note change undone",
        "not_geri_geldi":   "note restored",
        "geri_getirilecek_yok": "nothing to bring back",
        "silme_acik":       "delete mode: click a note or highlight (U / Ctrl-Z undoes, Esc leaves)",
        "silme_kapali":     "delete mode off",
        "silinecek_yok":    "nothing to delete there",
        "vurgu_geri_geldi": "deleted highlight restored",
        "yalniz_pdf":       "highlights work in PDFs only",
        "kalem_acik":       "pen on: drag, then Enter / colour key -> highlight, right click -> delete, Esc puts it down",
        "kalem_kapali":     "pen off",
        "secilecek_metin_yok": "no text to select here",
        "vurgulandi":       "highlighted: {metin}   (u: undo)",
        "vurgu_silindi":    "highlight deleted   (u: undo)",
        "belgede_vurgu_yok": "no highlights in this document  (v: pen, Shift+drag)",
        "aktarilacak_yok":  "no highlights or notes to export",
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
        "tepsi_durum":      "tray mode {durum}",
        "tepsi_ac":         "open",
        "tepsi_cik":        "quit rubric",
        "pencere_cercevesi": "window frame: {e}",
        "ac_baslik":        "open document",
        "ac_belgeler":      "Documents",
        "ac_tumu":          "All files",
        "yer_imi":          "bookmark: {ad} (p{s})",
        "yer_imi_yok":      "no bookmarks  ({tus}: bookmark this spot)",
        "yer_imi_var":      "already bookmarked here: {ad}",
        "mod_yer_imleri":   "[bookmarks]",
        "secim_bekliyor":   "\"{metin}\"  ->  enter: {varsayilan}   {tuslar}   ^c: copy   esc: drop",
        "secim_birakildi":  "selection dropped",
        "kopyalandi":       "copied: \"{metin}\"",
        "kopyalanacak_yok": "nothing to copy - shift+drag over the text first",
        "gece_modu_durum":  "night mode: {durum}",
        "tex_sec":          "open a .tex file",
        "tex_yeni":         "new file",
        "tex_dosya_ac":     "open a file",
        "tex_yeni_baslik":  "new .tex file",
        "tex_yeni_aciklama": "start a fresh .tex, pick where it lives",
        "tex_ac_aciklama":  "edit an existing .tex",
        "tex_karti_ipucu":  "j/k move   enter pick   n / o   esc cancel",
        "tex_acildi":       "tex: {ad} - ctrl-s compiles, esc goes to the pdf, T comes back",
        "tex_kapandi":      "tex mode closed, {ad} saved",
        "tex_kapali":       "tex mode is off (T opens it)",
        "tex_motor_yok":    "{motor} not found - install MiKTeX / TeX Live or :set tex-motoru",
        "tex_derleniyor":   "[compiling]",
        "tex_tamam":        "[ok {sn}s]",
        "tex_hatali":       "[error l.{satir}]",
        "tex_hatali_satirsiz": "[error]",
        "tex_kirli":        "[modified]",
        "tex_hata":         "latex: {dosya}:{satir}: {ileti}",
        "tex_hata_satirsiz": "latex: {ileti}",
        "tex_derlendi":     "tex: compiled in {sn}s -> {ad}",
        "tex_zaman_asimi":  "latex ran over {sn}s, stopped",
        "tex_yazilamadi":   "couldn't write {ad}: {e}",
        "tex_pdf_kilitli":  "couldn't update {ad} ({e}) - open in another program?",
        "renk_baslik":      "highlight colours",
        "renk_zaten":       "{tus} already paints {renk}",
        "renk_catisma":     "! {tus} currently paints {renk}, it will be taken from there",
        "renk_tusu_olmaz":  "! {tus} can't be a colour key (enter already paints the default)",
        "renk_atandi":      "highlight colour {renk}: {tus}",
        "renk_tema":        "theme",
        "renk_varsayilan_atandi": "enter now paints {renk}",
        "ipucu_renk":       "enter: bind key   space: make default   j/k: move   esc: back",
        "yazdiriliyor":     "printing {i}/{n} -> {yazici}   ({tus}: cancel)",
        "yazdirildi":       "printed: {sayfalar} -> {yazici}",
        "yazdirma_iptal":   "printing cancelled",
        "yazdirma_iptal_ediliyor": "cancelling the print job...",
        "yazdirilamadi":    "printing failed: {e}",
        "varsayilan_yazici_yok": "no default printer - pick one",
        "baglanti_var":     ("links: {n} on this page", "links: {n} on this page"),
        "baglanti_yok":     "links on - none on this page",
        "baglanti_kapali":  "links hidden",
        "mod_baglantilar":  "[links]",
        "baglanti_hedef_sayfa": "-> p. {n}",
        "baglanti_acildi":  "opened in the browser: {ne}",
        "baglanti_acilamadi": "could not open the link: {e}",
        "baglanti_guvensiz": "! link not followed (only http/https/mailto/ftp): {ne}",
        "baglanti_cozulemedi": "link target not found: {ne}",
        "baglanti_bilinmez": "link target unknown",
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
        "pdf_gerek":        "this works on PDFs only",
        "not_n":            ("{n} note", "{n} notes"),
        "birlestir_baslik": "PDFs to append after this document",
        "birlesik_ek":      "merged",
        "birlestirildi":    "{n} files merged, {sayfalar} -> {ad}",
        "temiz_ek":         "clean",
        "ustveri_yok":      "no metadata found - nothing written",
        "ustveri_silindi":  "removed: {alanlar} -> {ad}",
        "alan_title":       "title",
        "alan_author":      "author",
        "alan_subject":     "subject",
        "alan_keywords":    "keywords",
        "alan_creator":     "creator app",
        "alan_producer":    "producer",
        "alan_creationDate": "created date",
        "alan_modDate":     "modified date",
        "alan_trapped":     "trapped",
        "alan_xmp":         "XMP",
        "alan_yorum_yazari": ("{n} comment author", "{n} comment authors"),
        "karartma_acik":    "redact pen: drag a box or click a word - Enter writes the copy, Ctrl-Z drops the last box, Esc puts it down",
        "karartma_kapali":  "redact pen off",
        "karartma_bekliyor": "redact pen off - {n} still marked, X then Enter writes them",
        "karartma_eklendi": "{n} marked for redaction - Enter writes the copy",
        "karartma_kelime_yok": "no word here - drag a box instead",
        "karartma_yok":     "nothing marked for redaction (X: redact pen)",
        "karartma_geri":    "redaction mark removed",
        "karartilmis_ek":   "redacted",
        "karartildi":       "{n} areas blacked out, text removed -> {ad}",
        "karartma_sizdi":   "WARNING: text still readable in {n} area(s) of {ad}",
        "karart_bulundu":   "'{desen}': {n} matches marked - Enter writes the copy",
        "karart_kullanim":  "usage: :redact <word>",
        "karart_araniyor":  "searching '{desen}' to redact... {n}/{toplam}",
        "mod_karartma":     "[redact]",
        "mod_sayfa_duzeni": "[pages]",
        "duzen_baslik":     "$ pages  {ad}  {n}",
        "duzen_ipucu":      "hjkl move  HJKL carry  x delete  r/R rotate  v select  e extract  u undo  w write  q close",
        "duzen_degisti":    "[modified]",
        "duzen_ek":         "arranged",
        "ayri_ek":          "extract",
        "duzen_yazildi":    "{sayfalar} -> {ad}",
        "duzen_degismedi":  "nothing changed - nothing written",
        "duzen_hepsi":      "can't delete every page",
        "duzen_kaydedilmedi": "unsaved changes - q again drops them, w writes",
        "duzen_silindi":    "{sayfalar} deleted   (u: undo)",
        "duzen_geri_yok":   "nothing to undo",
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
        "yan_sol":          "left",
        "yan_sag":          "right",
        "bolme_belge_yok":  "no document to move",
        "bolme_yok":        "not split - <A-Right> / <A-Left> throws a document to a side",
        "bolme_zaten":      "already in the {yan} pane",
        "bolmeye_tasindi":  "{ad} -> {yan} pane",
        "bolmeye_gecildi":  "{yan} pane",
        "bolme_kapandi":    ("pane closed, {n} document moved here",
                             "pane closed, {n} documents moved here"),
        "bolme_belgesiz_kapandi": "closed: {ad}  -  pane closed too  ({tus}: reopen)",
        "son_belge_kapandi": "closed: {ad}  -  no documents left  ({tus}: reopen, o: open, Q: quit)",
        "geri_acildi":      "reopened: {ad}",
        "geri_acildi_daha": "reopened: {ad}  ({n} more)",
        "geri_acilacak_yok": "no closed document to reopen",
        "yazici_baslik":    "printer",
        "yazici_sistem":    "Windows default",
        "yazici_secildi":   "print goes to: {ad}",
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
        "not_eklendi":      "not eklendi",
        "not_guncellendi":  "not güncellendi",
        "not_silindi":      "not silindi",
        "not_sayfa_disi":   "önce imleci bir sayfanın üstüne getir",
        "not_istem":        "not>",
        "not_geri_alindi":  "not değişikliği geri alındı",
        "not_geri_geldi":   "not geri geldi",
        "geri_getirilecek_yok": "geri getirilecek bir şey yok",
        "silme_acik":       "silme kipi: not ya da vurguya tıkla (U / Ctrl-Z geri getirir, Esc çıkar)",
        "silme_kapali":     "silme kipi kapandı",
        "silinecek_yok":    "orada silinecek bir şey yok",
        "vurgu_geri_geldi": "silinen vurgu geri geldi",
        "yalniz_pdf":       "vurgu yalnızca PDF'te",
        "kalem_acik":       "kalem açık: sürükle, sonra Enter / renk tuşu -> vurgula, sağ tık -> sil, Esc bırak",
        "kalem_kapali":     "kalem kapalı",
        "secilecek_metin_yok": "burada seçilecek metin yok",
        "vurgulandi":       "vurgulandı: {metin}   (u: geri al)",
        "vurgu_silindi":    "vurgu silindi   (u: geri al)",
        "belgede_vurgu_yok": "bu belgede vurgu yok  (v: kalem, Shift+sürükle)",
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
        "tepsi_durum":      "tepsi modu {durum}",
        "tepsi_ac":         "aç",
        "tepsi_cik":        "rubric'ten çık",
        "pencere_cercevesi": "pencere çerçevesi: {e}",
        "ac_baslik":        "belge aç",
        "ac_belgeler":      "Belgeler",
        "ac_tumu":          "Tümü",
        "yer_imi":          "yer imi: {ad} (s{s})",
        "yer_imi_yok":      "yer imi yok  ({tus}: buraya yer imi koy)",
        "yer_imi_var":      "burada zaten yer imi var: {ad}",
        "mod_yer_imleri":   "[yer imleri]",
        "secim_bekliyor":   "\"{metin}\"  ->  enter: {varsayilan}   {tuslar}   ^c: kopyala   esc: bırak",
        "secim_birakildi":  "seçim bırakıldı",
        "kopyalandi":       "kopyalandı: \"{metin}\"",
        "kopyalanacak_yok": "kopyalanacak bir şey yok - önce shift+sürükle ile seç",
        "gece_modu_durum":  "gece modu: {durum}",
        "tex_sec":          ".tex dosyası aç",
        "tex_yeni":         "yeni dosya",
        "tex_dosya_ac":     "dosya aç",
        "tex_yeni_baslik":  "yeni .tex dosyası",
        "tex_yeni_aciklama": "sıfırdan bir .tex başlat, yerini seç",
        "tex_ac_aciklama":  "var olan bir .tex'i düzenle",
        "tex_karti_ipucu":  "j/k gez   enter seç   n / o   esc vazgeç",
        "tex_acildi":       "tex: {ad} - ctrl-s derler, esc pdf'e geçer, T geri getirir",
        "tex_kapandi":      "tex modu kapandı, {ad} kaydedildi",
        "tex_kapali":       "tex modu kapalı (T açar)",
        "tex_motor_yok":    "{motor} bulunamadı - MiKTeX / TeX Live kur ya da :set tex-motoru",
        "tex_derleniyor":   "[derleniyor]",
        "tex_tamam":        "[tamam {sn}sn]",
        "tex_hatali":       "[hata s.{satir}]",
        "tex_hatali_satirsiz": "[hata]",
        "tex_kirli":        "[değişti]",
        "tex_hata":         "latex: {dosya}:{satir}: {ileti}",
        "tex_hata_satirsiz": "latex: {ileti}",
        "tex_derlendi":     "tex: {sn}sn'de derlendi -> {ad}",
        "tex_zaman_asimi":  "latex {sn}sn'yi aştı, durduruldu",
        "tex_yazilamadi":   "{ad} yazılamadı: {e}",
        "tex_pdf_kilitli":  "{ad} güncellenemedi ({e}) - başka bir programda mı açık?",
        "renk_baslik":      "vurgu renkleri",
        "renk_zaten":       "{tus} zaten {renk} boyuyor",
        "renk_catisma":     "! {tus} şu an {renk} boyuyor, ondan alınacak",
        "renk_tusu_olmaz":  "! {tus} renk tuşu olamaz (enter zaten varsayılanı koyar)",
        "renk_atandi":      "vurgu rengi {renk}: {tus}",
        "renk_tema":        "tema",
        "renk_varsayilan_atandi": "enter artık {renk} boyuyor",
        "ipucu_renk":       "enter: tuş ata   boşluk: varsayılan yap   j/k: gez   esc: geri",
        "yazdiriliyor":     "yazdırılıyor {i}/{n} -> {yazici}   ({tus}: iptal)",
        "yazdirildi":       "yazdırıldı: {sayfalar} -> {yazici}",
        "yazdirma_iptal":   "yazdırma iptal edildi",
        "yazdirma_iptal_ediliyor": "yazdırma iptal ediliyor...",
        "yazdirilamadi":    "yazdırılamadı: {e}",
        "varsayilan_yazici_yok": "varsayılan yazıcı yok - seçmen gerekiyor",
        "baglanti_var":     "bağlantılar: bu sayfada {n}",
        "baglanti_yok":     "bağlantılar açık - bu sayfada yok",
        "baglanti_kapali":  "bağlantılar gizlendi",
        "mod_baglantilar":  "[bağlantılar]",
        "baglanti_hedef_sayfa": "-> s. {n}",
        "baglanti_acildi":  "tarayıcıda açıldı: {ne}",
        "baglanti_acilamadi": "bağlantı açılamadı: {e}",
        "baglanti_guvensiz": "! bağlantı açılmadı (yalnızca http/https/mailto/ftp): {ne}",
        "baglanti_cozulemedi": "bağlantının hedefi bulunamadı: {ne}",
        "baglanti_bilinmez": "bağlantının hedefi bilinmiyor",
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
        "pdf_gerek":        "bu yalnızca PDF'te çalışır",
        "not_n":            "{n} not",
        "aktarildi":        "{vurgular} -> {ad}",
        "aktarilacak_yok":  "aktarılacak vurgu ya da not yok",
        "birlestir_baslik": "bu belgenin arkasına eklenecek PDF'ler",
        "birlesik_ek":      "birlesik",
        "birlestirildi":    "{n} dosya birleşti, {sayfalar} -> {ad}",
        "temiz_ek":         "temiz",
        "ustveri_yok":      "üstveri bulunamadı - bir şey yazılmadı",
        "ustveri_silindi":  "silindi: {alanlar} -> {ad}",
        "alan_title":       "başlık",
        "alan_author":      "yazar",
        "alan_subject":     "konu",
        "alan_keywords":    "anahtar sözcükler",
        "alan_creator":     "oluşturan program",
        "alan_producer":    "üretici",
        "alan_creationDate": "oluşturma tarihi",
        "alan_modDate":     "değiştirme tarihi",
        "alan_trapped":     "trapped",
        "alan_xmp":         "XMP",
        "alan_yorum_yazari": "{n} yorum yazarı",
        "karartma_acik":    "karartma kalemi: kutu sürükle ya da kelimeye tıkla - Enter kopyayı yazar, Ctrl-Z son kutuyu atar, Esc bırakır",
        "karartma_kapali":  "karartma kalemi kapalı",
        "karartma_bekliyor": "karartma kalemi kapalı - {n} işaret duruyor, X sonra Enter yazar",
        "karartma_eklendi": "{n} alan işaretli - Enter karartılmış kopyayı yazar",
        "karartma_kelime_yok": "burada kelime yok - kutu sürükle",
        "karartma_yok":     "karartılacak bir şey işaretlenmedi (X: karartma kalemi)",
        "karartma_geri":    "karartma işareti kaldırıldı",
        "karartilmis_ek":   "karartilmis",
        "karartildi":       "{n} alan karartıldı, metin silindi -> {ad}",
        "karartma_sizdi":   "DİKKAT: {ad} içinde {n} alanda metin hâlâ okunuyor",
        "karart_bulundu":   "'{desen}': {n} eşleşme işaretlendi - Enter kopyayı yazar",
        "karart_kullanim":  "kullanım: :karart <kelime>",
        "karart_araniyor":  "karartmak için '{desen}' aranıyor... {n}/{toplam}",
        "mod_karartma":     "[karartma]",
        "mod_sayfa_duzeni": "[sayfalar]",
        "duzen_baslik":     "$ sayfalar  {ad}  {n}",
        "duzen_ipucu":      "hjkl gez  HJKL taşı  x sil  r/R döndür  v seç  e ayır  u geri  w yaz  q kapat",
        "duzen_degisti":    "[değişti]",
        "duzen_ek":         "duzenli",
        "ayri_ek":          "secilen",
        "duzen_yazildi":    "{sayfalar} -> {ad}",
        "duzen_degismedi":  "değişiklik yok - bir şey yazılmadı",
        "duzen_hepsi":      "bütün sayfalar silinemez",
        "duzen_kaydedilmedi": "kaydedilmemiş değişiklik - yine q atar, w yazar",
        "duzen_silindi":    "{sayfalar} silindi   (u: geri al)",
        "duzen_geri_yok":   "geri alınacak bir şey yok",
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
        "yan_sol":          "sol",
        "yan_sag":          "sağ",
        "bolme_belge_yok":  "taşınacak belge yok",
        "bolme_yok":        "bölme yok - <A-Right> / <A-Left> belgeyi bir yana atar",
        "bolme_zaten":      "zaten {yan} bölmede",
        "bolmeye_tasindi":  "{ad} -> {yan} bölme",
        "bolmeye_gecildi":  "{yan} bölme",
        "bolme_kapandi":    "bölme kapandı, {n} belge bu listeye katıldı",
        "bolme_belgesiz_kapandi": "kapatıldı: {ad}  -  bölme de kapandı  ({tus}: geri aç)",
        "son_belge_kapandi": "kapatıldı: {ad}  -  açık belge kalmadı  ({tus}: geri aç, o: aç, Q: çık)",
        "geri_acildi":      "geri açıldı: {ad}",
        "geri_acildi_daha": "geri açıldı: {ad}  (sırada {n} tane daha)",
        "geri_acilacak_yok": "geri açılacak kapanmış belge yok",
        "yazici_baslik":    "yazıcı",
        "yazici_sistem":    "Windows varsayılanı",
        "yazici_secildi":   "yazdır bundan sonra: {ad}",
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
        "not_eklendi":      "Notiz hinzugefügt",
        "not_guncellendi":  "Notiz aktualisiert",
        "not_silindi":      "Notiz gelöscht",
        "not_sayfa_disi":   "zeige zuerst auf eine Seite",
        "not_istem":        "Notiz>",
        "not_geri_alindi":  "Notizänderung rückgängig gemacht",
        "not_geri_geldi":   "Notiz wiederhergestellt",
        "geri_getirilecek_yok": "nichts zum Zurückholen",
        "silme_acik":       "Löschmodus: auf Notiz oder Markierung klicken (U / Strg-Z holt zurück, Esc beendet)",
        "silme_kapali":     "Löschmodus aus",
        "silinecek_yok":    "dort gibt es nichts zu löschen",
        "vurgu_geri_geldi": "gelöschte Markierung wiederhergestellt",
        "yalniz_pdf":       "Markierungen nur in PDFs",
        "kalem_acik":       "Stift an: ziehen, dann Enter / Farbtaste -> markieren, Rechtsklick -> löschen, Esc legt ihn weg",
        "kalem_kapali":     "Stift aus",
        "secilecek_metin_yok": "hier gibt es keinen Text zum Auswählen",
        "vurgulandi":       "markiert: {metin}   (u: rückgängig)",
        "vurgu_silindi":    "Markierung gelöscht   (u: rückgängig)",
        "belgede_vurgu_yok": "keine Markierungen in diesem Dokument  (v: Stift, Shift+Ziehen)",
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
        "tepsi_durum":      "Tray-Modus {durum}",
        "tepsi_ac":         "öffnen",
        "tepsi_cik":        "rubric beenden",
        "pencere_cercevesi": "Fensterrahmen: {e}",
        "ac_baslik":        "Dokument öffnen",
        "ac_belgeler":      "Dokumente",
        "ac_tumu":          "Alle Dateien",
        "yer_imi":          "Lesezeichen: {ad} (S.{s})",
        "yer_imi_yok":      "keine Lesezeichen  ({tus}: Lesezeichen hier setzen)",
        "yer_imi_var":      "hier ist schon ein Lesezeichen: {ad}",
        "mod_yer_imleri":   "[Lesezeichen]",
        "secim_bekliyor":   "\"{metin}\"  ->  enter: {varsayilan}   {tuslar}   ^c: kopieren   esc: verwerfen",
        "secim_birakildi":  "Auswahl verworfen",
        "kopyalandi":       "kopiert: \"{metin}\"",
        "kopyalanacak_yok": "nichts zu kopieren - erst mit Shift+Ziehen auswählen",
        "gece_modu_durum":  "Nachtmodus: {durum}",
        "tex_sec":          ".tex-Datei öffnen",
        "tex_yeni":         "neue Datei",
        "tex_dosya_ac":     "Datei öffnen",
        "tex_yeni_baslik":  "neue .tex-Datei",
        "tex_yeni_aciklama": "neue .tex beginnen, Speicherort wählen",
        "tex_ac_aciklama":  "vorhandene .tex bearbeiten",
        "tex_karti_ipucu":  "j/k bewegen   Enter wählen   n / o   Esc abbrechen",
        "tex_acildi":       "tex: {ad} - Strg-S kompiliert, Esc geht zum PDF, T zurück",
        "tex_kapandi":      "TeX-Modus geschlossen, {ad} gespeichert",
        "tex_kapali":       "TeX-Modus ist aus (T öffnet ihn)",
        "tex_motor_yok":    "{motor} nicht gefunden - MiKTeX / TeX Live installieren oder :set tex-motoru",
        "tex_derleniyor":   "[kompiliert]",
        "tex_tamam":        "[ok {sn}s]",
        "tex_hatali":       "[Fehler Z.{satir}]",
        "tex_hatali_satirsiz": "[Fehler]",
        "tex_kirli":        "[geändert]",
        "tex_hata":         "latex: {dosya}:{satir}: {ileti}",
        "tex_hata_satirsiz": "latex: {ileti}",
        "tex_derlendi":     "tex: in {sn}s kompiliert -> {ad}",
        "tex_zaman_asimi":  "latex lief über {sn}s, gestoppt",
        "tex_yazilamadi":   "{ad} konnte nicht geschrieben werden: {e}",
        "tex_pdf_kilitli":  "{ad} nicht aktualisiert ({e}) - in einem anderen Programm offen?",
        "renk_baslik":      "Markerfarben",
        "renk_zaten":       "{tus} markiert schon {renk}",
        "renk_catisma":     "! {tus} markiert gerade {renk} und wird dort entfernt",
        "renk_tusu_olmaz":  "! {tus} geht nicht als Farbtaste (Enter setzt schon die Standardfarbe)",
        "renk_atandi":      "Markerfarbe {renk}: {tus}",
        "renk_tema":        "Thema",
        "renk_varsayilan_atandi": "Enter markiert jetzt {renk}",
        "ipucu_renk":       "enter: Taste zuweisen   leer: Standard   j/k: bewegen   esc: zurück",
        "yazdiriliyor":     "drucke {i}/{n} -> {yazici}   ({tus}: abbrechen)",
        "yazdirildi":       "gedruckt: {sayfalar} -> {yazici}",
        "yazdirma_iptal":   "Druck abgebrochen",
        "yazdirma_iptal_ediliyor": "Druck wird abgebrochen...",
        "yazdirilamadi":    "Drucken fehlgeschlagen: {e}",
        "varsayilan_yazici_yok": "kein Standarddrucker - bitte auswählen",
        "baglanti_var":     ("Links: {n} auf dieser Seite", "Links: {n} auf dieser Seite"),
        "baglanti_yok":     "Links an - keine auf dieser Seite",
        "baglanti_kapali":  "Links verborgen",
        "mod_baglantilar":  "[Links]",
        "baglanti_hedef_sayfa": "-> S. {n}",
        "baglanti_acildi":  "im Browser geöffnet: {ne}",
        "baglanti_acilamadi": "Link konnte nicht geöffnet werden: {e}",
        "baglanti_guvensiz": "! Link nicht geöffnet (nur http/https/mailto/ftp): {ne}",
        "baglanti_cozulemedi": "Linkziel nicht gefunden: {ne}",
        "baglanti_bilinmez": "Linkziel unbekannt",
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
        "pdf_gerek":        "das geht nur mit PDFs",
        "not_n":            ("{n} Notiz", "{n} Notizen"),
        "aktarildi":        "{vurgular} -> {ad}",
        "aktarilacak_yok":  "keine Markierungen oder Notizen zum Exportieren",
        "birlestir_baslik": "PDFs, die hinten angehängt werden",
        "birlesik_ek":      "zusammen",
        "birlestirildi":    "{n} Dateien zusammengefügt, {sayfalar} -> {ad}",
        "temiz_ek":         "bereinigt",
        "ustveri_yok":      "keine Metadaten gefunden - nichts geschrieben",
        "ustveri_silindi":  "entfernt: {alanlar} -> {ad}",
        "alan_title":       "Titel",
        "alan_author":      "Autor",
        "alan_subject":     "Thema",
        "alan_keywords":    "Stichwörter",
        "alan_creator":     "Erstellerprogramm",
        "alan_producer":    "Produzent",
        "alan_creationDate": "Erstelldatum",
        "alan_modDate":     "Änderungsdatum",
        "alan_trapped":     "Trapped",
        "alan_xmp":         "XMP",
        "alan_yorum_yazari": ("{n} Kommentarautor", "{n} Kommentarautoren"),
        "karartma_acik":    "Schwärzstift: Rahmen ziehen oder Wort klicken - Enter schreibt die Kopie, Strg-Z nimmt den letzten zurück, Esc legt ihn weg",
        "karartma_kapali":  "Schwärzstift aus",
        "karartma_bekliyor": "Schwärzstift aus - {n} noch markiert, X dann Enter schreibt sie",
        "karartma_eklendi": "{n} zum Schwärzen markiert - Enter schreibt die Kopie",
        "karartma_kelime_yok": "hier ist kein Wort - Rahmen ziehen",
        "karartma_yok":     "nichts zum Schwärzen markiert (X: Schwärzstift)",
        "karartma_geri":    "Schwärzungsmarke entfernt",
        "karartilmis_ek":   "geschwaerzt",
        "karartildi":       "{n} Bereiche geschwärzt, Text entfernt -> {ad}",
        "karartma_sizdi":   "WARNUNG: in {ad} ist in {n} Bereich(en) noch Text lesbar",
        "karart_bulundu":   "'{desen}': {n} Treffer markiert - Enter schreibt die Kopie",
        "karart_kullanim":  "Aufruf: :schwaerzen <Wort>",
        "karart_araniyor":  "suche '{desen}' zum Schwärzen... {n}/{toplam}",
        "mod_karartma":     "[Schwärzen]",
        "mod_sayfa_duzeni": "[Seiten]",
        "duzen_baslik":     "$ Seiten  {ad}  {n}",
        "duzen_ipucu":      "hjkl bewegen  HJKL tragen  x löschen  r/R drehen  v wählen  e herauslösen  u zurück  w schreiben  q schließen",
        "duzen_degisti":    "[geändert]",
        "duzen_ek":         "geordnet",
        "ayri_ek":          "auszug",
        "duzen_yazildi":    "{sayfalar} -> {ad}",
        "duzen_degismedi":  "nichts geändert - nichts geschrieben",
        "duzen_hepsi":      "nicht alle Seiten löschbar",
        "duzen_kaydedilmedi": "ungespeicherte Änderungen - nochmal q verwirft, w schreibt",
        "duzen_silindi":    "{sayfalar} gelöscht   (u: rückgängig)",
        "duzen_geri_yok":   "nichts rückgängig zu machen",
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
        "yan_sol":          "linken",
        "yan_sag":          "rechten",
        "bolme_belge_yok":  "kein Dokument zum Verschieben",
        "bolme_yok":        "nicht geteilt - <A-Right> / <A-Left> wirft ein Dokument zur Seite",
        "bolme_zaten":      "schon im {yan} Bereich",
        "bolmeye_tasindi":  "{ad} -> {yan} Bereich",
        "bolmeye_gecildi":  "{yan} Bereich",
        "bolme_kapandi":    ("Bereich geschlossen, {n} Dokument übernommen",
                             "Bereich geschlossen, {n} Dokumente übernommen"),
        "bolme_belgesiz_kapandi": "geschlossen: {ad}  -  Bereich ebenfalls geschlossen  ({tus}: wieder öffnen)",
        "son_belge_kapandi": "geschlossen: {ad}  -  keine Dokumente mehr  ({tus}: wieder öffnen, o: öffnen, Q: beenden)",
        "geri_acildi":      "wieder geöffnet: {ad}",
        "geri_acildi_daha": "wieder geöffnet: {ad}  (noch {n})",
        "geri_acilacak_yok": "kein geschlossenes Dokument zum Wiederöffnen",
        "yazici_baslik":    "Drucker",
        "yazici_sistem":    "Windows-Standard",
        "yazici_secildi":   "drucken geht an: {ad}",
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
        "not-ekle": "note",
        "geri-getir": "restore",
        "silme-kipi": "delete-mode",
        "vurgu-geri-al": "undo-highlight", "vurgulari-aktar": "export-highlights",
        "sayfa-duzeni": "organize-pages", "birlestir": "merge",
        "karartma-kalemi": "redact-pen", "karartmayi-uygula": "apply-redaction",
        "ustveri-temizle": "strip-metadata",
        "kopyala": "copy", "tex-modu": "tex", "tex-derle": "tex-compile",
        "tex-kapat": "tex-close",
        "ac": "open-file", "yeniden-yukle": "reload", "komut-modu": "command-line",
        "cik": "quit",
        "sonraki-belge": "next-doc", "onceki-belge": "prev-doc",
        "belgeyi-kapat": "close-doc", "belgeler": "documents",
        "kapanani-ac": "reopen-closed", "geri-acma-siniri": "reopen-limit",
        "bolme-saga": "pane-right", "bolme-sola": "pane-left",
        "bolme-gec": "pane-switch", "bolme-tek": "pane-only",
        "yazici": "printer", "tema": "theme", "tepsi": "tray",
        "vurgu-renkleri": "highlight-colours", "yer-imi-koy": "add-bookmark",
        "yer-imleri": "bookmarks", "yazdir": "print", "yazdir-sec": "print-dialog",
        "baglantilar": "show-links",
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
        "not-ekle": "not",
        "geri-getir": "geri-getir",
        "silme-kipi": "silme-kipi",
        "vurgu-geri-al": "vurgu-geri-al", "vurgulari-aktar": "vurguları-aktar",
        "sayfa-duzeni": "sayfa-düzeni", "birlestir": "birleştir",
        "karartma-kalemi": "karartma-kalemi", "karartmayi-uygula": "karartmayı-uygula",
        "ustveri-temizle": "üstveri-temizle",
        "kopyala": "kopyala", "tex-modu": "tex-modu", "tex-derle": "tex-derle",
        "tex-kapat": "tex-kapat",
        "ac": "aç", "yeniden-yukle": "yeniden-yükle", "komut-modu": "komut-satırı",
        "cik": "çık",
        "sonraki-belge": "sonraki-belge", "onceki-belge": "önceki-belge",
        "belgeyi-kapat": "belgeyi-kapat", "belgeler": "belgeler",
        "kapanani-ac": "kapananı-aç", "geri-acma-siniri": "geri-açma-sınırı",
        "bolme-saga": "bölme-sağa", "bolme-sola": "bölme-sola",
        "bolme-gec": "bölme-geç", "bolme-tek": "bölme-tek",
        "yazici": "yazıcı", "tema": "tema", "tepsi": "tepsi",
        "vurgu-renkleri": "vurgu-renkleri", "yer-imi-koy": "yer-imi-koy",
        "yer-imleri": "yer-imleri", "yazdir": "yazdır", "yazdir-sec": "yazdır-seç",
        "baglantilar": "bağlantılar",
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
        "not-ekle": "notiz",
        "geri-getir": "zurückholen",
        "silme-kipi": "löschmodus",
        "vurgu-geri-al": "markierung-rückgängig",
        "vurgulari-aktar": "markierungen-exportieren",
        "sayfa-duzeni": "seiten-ordnen", "birlestir": "zusammenfügen",
        "karartma-kalemi": "schwärzstift", "karartmayi-uygula": "schwärzung-anwenden",
        "ustveri-temizle": "metadaten-entfernen",
        "kopyala": "kopieren", "tex-modu": "tex-modus", "tex-derle": "tex-kompilieren",
        "tex-kapat": "tex-schließen",
        "ac": "öffnen", "yeniden-yukle": "neu-laden", "komut-modu": "befehlszeile",
        "cik": "beenden",
        "sonraki-belge": "nächstes-dokument", "onceki-belge": "voriges-dokument",
        "belgeyi-kapat": "dokument-schließen", "belgeler": "dokumente",
        "kapanani-ac": "wieder-öffnen", "geri-acma-siniri": "wiederöffnen-limit",
        "bolme-saga": "bereich-rechts", "bolme-sola": "bereich-links",
        "bolme-gec": "bereich-wechseln", "bolme-tek": "bereich-einzeln",
        "yazici": "drucker", "tepsi": "tray",
        "tema": "thema",
        "vurgu-renkleri": "markerfarben", "yer-imi-koy": "lesezeichen-setzen",
        "yer-imleri": "lesezeichen", "yazdir": "drucken", "yazdir-sec": "drucken-dialog",
        "baglantilar": "links-zeigen",
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


def rgb(onaltili: str) -> tuple[float, float, float]:
    """`#rrggbb` -> 0-1 araliginda (r, g, b)."""
    h = onaltili.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _parlaklik(onaltili: str) -> float:
    """WCAG goreli parlaklik; palette tema satirini kendi renginde yazmadan
    once okunur mu diye bakmak icin."""
    def kanal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (kanal(c) for c in rgb(onaltili))
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


def tema_kimligi(ad: str) -> str:
    """Temanin her dildeki adi (neon, eis, tema-buz) -> TEMALAR anahtari.
    Taninmazsa katlanmis hali doner; TEMALAR'da olup olmadigina cagiran bakar."""
    kimlik = komut_kimligi(ad)
    return kimlik[5:] if kimlik.startswith("tema-") else katla(ad)

# Paletten yapilan tus atamalari rubricrc'nin sonunda bu isaretlerin arasinda
# toplanir; boylece kullanicinin elle yazdigi satirlara hic dokunulmaz.
RC_BLOK_BAS = "# >>> rubric: eylem paletinden yazildi >>>"
RC_BLOK_SON = "# <<< rubric <<<"


def renk(anahtar: str) -> tuple[float, float, float]:
    """`#rrggbb` ayarini PyMuPDF'in bekledigi 0-1 ucluye cevirir.

    Tus karti ile ikon betigi paleti kendi iclerinde tekrar yazmasin diye
    burada: tema degisince onlar da dondu sayilir.
    """
    return rgb(VARSAYILAN_AYAR[anahtar])


# ---------------------------------------------------------------------------
# Baglanti capasi
#
# Bir ic baglantinin PDF'teki hedefi cogu zaman yalnizca "su sayfa"dir: dizin
# girdisi `/Fit`, LaTeX disi uretilmis kitaplarin hepsi oyle. PyMuPDF bunu
# `to = Point(0, 0)` diye verir, yani sayfada nereye gidilecegi yazmaz.
# Sonuc: "Fig. 2.18"e tiklayan sayfanin tepesine duser - ustelik hedef ayni
# sayfaysa hicbir sey olmamis gibi gorunur.
#
# Cozum: hedefi **belgenin kendi metninden** bul. Tiklanan yazidan etiket
# cikarilir ("Fig. 2.18a" -> 2.18a) ve hedef sayfada o etiketle **baslayan**
# satir aranir - altyazi da ("Figure 2.18 ...") problem numarasi da
# ("2.23 BIO Automobile Airbags") oyle yazilir. Bulunursa oraya gidilir ve
# yer bir an isaretlenir; bulunamazsa eski davranis: sayfanin tepesi.
#
# Olculdu (temiz2.pdf, 40 rastgele sayfadaki 184 `/Fit` baglantisi): hepsi
# capasini buldu. Desenler uc dilde; sayi "P25.59" gibi harf onekli ve
# "5.38c" gibi alt sekil harfli olabilir, harfli bulunamazsa harfsizi denenir.
# ---------------------------------------------------------------------------

_CAPA_SAYI = r"([A-Za-z]?[0-9]+(?:[.\-][0-9]+)*[a-z]?)"
CAPA_DESENLERI: list[tuple[str, tuple[str, ...]]] = [
    (r"\b(?:figs?|figures?|sekil|şekil|abb|abbildung)\b\.?\s*" + _CAPA_SAYI,
     ("Figure {n}", "Fig. {n}", "Şekil {n}", "Abbildung {n}")),
    (r"\b(?:tables?|tablo|tabelle|tab)\b\.?\s*" + _CAPA_SAYI,
     ("Table {n}", "Tablo {n}", "Tabelle {n}")),
    (r"\b(?:eqs?|eqn|equations?|denklem|gleichung)\b\.?\s*\(?" + _CAPA_SAYI,
     ("({n})", "Equation {n}", "Denklem {n}")),
    (r"\b(?:examples?|örnek|ornek|beispiel)\b\.?\s*" + _CAPA_SAYI,
     ("Example {n}", "Örnek {n}", "Beispiel {n}")),
    (r"\b(?:problems?|exercises?|alıştırma|alistirma|aufgabe)\b\.?\s*" + _CAPA_SAYI,
     ("Problem {n}", "Exercise {n}", "Alıştırma {n}", "Aufgabe {n}")),
    (r"\b(?:sections?|sec|chapters?|chap|bölüm|bolum|kapitel|abschnitt)\b\.?\s*"
     + _CAPA_SAYI, ()),
    # Kaynakca: LaTeX'in \cite'i "[12]" yazar, hedefteki girdi de oyle baslar.
    (r"\[([0-9]{1,3})\]", ("[{n}]",)),
]
# Anahtar kelimesiz baglanti: bastaki sayi (dizin girdisi, "2.5 FREELY FALLING")
_CAPA_BAS_SAYI = re.compile(r"^\(?" + _CAPA_SAYI + r"\)?")
# Kaynakcada sayi yoksa yazar adi: "(Smith, 2019)" -> hedefte "Smith" ile baslayan satir
_CAPA_YAZAR = re.compile(r"\b([A-ZÇĞİÖŞÜ][\w'\-]{2,})")


def capa_etiketleri(metin: str) -> tuple[list[str], str | None]:
    """Tiklanan yazidan hedef satirin baslangic adaylarini cikarir.

    Doner: (genisletilmis adaylar, ciplak etiket). Genisletilmis adaylar
    ("Figure 2.18") satir icinde de aranabilir; ciplak etiket ("2.18") cok
    siradan oldugu icin yalnizca satir basinda sayilir.
    """
    t = " ".join(metin.split())
    for desen, kaliplar in CAPA_DESENLERI:
        m = re.search(desen, t, re.I)
        if not m:
            continue
        n = m.group(1)
        adaylar = [k.format(n=n) for k in kaliplar]
        # "Fig. 5.38c" -> altyazi cogu kitapta harfsiz: "Figure 5.38"
        if n[-1:].isalpha() and len(n) > 1 and n[-2].isdigit():
            adaylar += [k.format(n=n[:-1]) for k in kaliplar]
            return adaylar, n[:-1]
        return adaylar, n
    m = _CAPA_BAS_SAYI.match(t)
    if m:
        return [], m.group(1)
    m = _CAPA_YAZAR.search(t)
    return ([], m.group(1)) if m else ([], None)


# Tex modunda yeni dosyanin ilk hali ve derlemenin ust siniri (sn).
# Govdede bir satir olmali: bos belgeden latex PDF uretmiyor ("No pages of output").
TEX_SABLONU = "\\documentclass{article}\n\\begin{document}\n\nHello, world.\n\n\\end{document}\n"
TEX_ZAMAN_ASIMI = 90
# -file-line-error bicimi: "./ana.tex:12: Undefined control sequence."
_TEX_HATA = re.compile(r"^(.*?\.\w+):(\d+): (.*)$", re.M)
# Satir satir boyama; sira onemli, sonraki oncekinin ustune biner.
_TEX_DESENLER = (
    ("tex_parantez", re.compile(r"[{}\[\]]")),
    ("tex_mat", re.compile(r"\$\$.*?\$\$|\$(?:\\.|[^$\\])+\$")),
    ("tex_komut", re.compile(r"\\(?:[A-Za-z@]+\*?|.)")),
    ("tex_yorum", re.compile(r"(?<!\\)%.*")),
)


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
            kimlik = tema_kimligi(d)                # her dildeki ad da olur: neon, eis
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
# Bolme (sol / sag gorunum)
#
# Iki belgeyi yan yana okumak icin. Uygulamanin geri kalani tek belge biliyor
# gibi yazilmis - `self.belge`, `self.tuval`, `self.zoom`, `self.yerler` ...
# Bunlarin hepsi **bakilan bolmenin** alanlari olsun diye asagida birer
# ozellige (property) cevriliyor: `self.belge` = `self.bolmeler[self.etkin].belge`.
# Boylece ciz / ara / vurgula / yazdir kodunun tek satiri degismeden, her
# bolme kendi belgesini, kendi yakinlastirmasini, kendi aramasini tasiyor.
# Bakilmayan bolmeyi cizmek icin `_bolmede(b)` etkin bolmeyi bir islik
# degistirir.
#
# En cok iki bolme var (sol = 0, sag = 1); ucuncusu istenmedi ve durum cubugu
# ile oturum kaydini gereksiz karmasiklastirirdi.
# ---------------------------------------------------------------------------

BOLME_ALANLARI = (
    "cerceve", "tuval",
    # belge ve listesi (her bolmenin kendi <C-Left>/<C-Right> sirasi var)
    "belge", "pdf_yolu", "belgeler", "zoom", "donme", "sigdir", "sutunlar",
    # duzen
    "satirlar", "yerler", "_altlar", "toplam_yukseklik", "toplam_genislik",
    "_olcu", "_hedef_zoom", "_zoom_ekran", "_zoom_isi", "_komsu_isi",
    "onbellek", "tuval_ogeleri", "aktif_sayfa",
    # arama
    "bulgular", "bulgu_no", "son_desen", "arama_yonu", "arama_kuyrugu",
    "arama_kimlik", "_aktif_bulgu", "_ilk_atlama",
    # ziplama listesi ve isaretler
    "zipla_gecmis", "zipla_ileri", "isaretler",
    # vurgular
    "vurgular", "_vurgu_xref", "vurgu_gecmisi", "kalem", "silme_kipi",
    "_secim", "_kelimeler",
    "_bekleyen_vurgu",
    # karartma (X)
    "karartma_acik", "karartmalar", "_karartma_cizimi",
    # kenar notlari
    "notlar", "_imlecteki_not", "_duzenlenen_not", "geri_yigini",
    # baglantilar
    "baglantilar_acik", "_baglantilar", "_baglanti_cizili", "_imlecteki_baglanti",
    "_baglanti_adayi", "_basis_noktasi", "_surukleniyor", "_satir_metinleri",
    "_capa", "_capa_isi",
    # icindekiler
    "_icindekiler_hatira",
)


class Bolme:
    """Tek bir gorunumun butun durumu. Alanlari Rubric.__init__ doldurur."""

    __slots__ = BOLME_ALANLARI

    def __init__(self):
        for ad in BOLME_ALANLARI:
            setattr(self, ad, None)


# ---------------------------------------------------------------------------
# Uygulama
# ---------------------------------------------------------------------------

class Rubric(tk.Tk):

    def __init__(self, acilacak: str | list[str] | None = None):
        super().__init__()

        # Once bolmeler: asagidaki `self.belge = ...` gibi atamalarin hepsi
        # BOLME_ALANLARI ozelligi uzerinden etkin bolmeye yazilir.
        self.bolmeler: list[Bolme] = [Bolme()]
        self.etkin: int = 0

        self.yapi = Yapilandirma()
        self.yapi.yukle()
        self.ayar = self.yapi.ayar
        self.tuslar = self.yapi.tuslar
        self.kalici = Durum()
        self.ayar["yazitipi"] = self.yazitipi_sec(self.ayar["yazitipi"])

        # --- belge / gorunum durumu ---
        # Bunlarin hepsi bolmenin alani (bkz. BOLME_ALANLARI); varsayilanlari
        # _bolmeyi_sifirla veriyor ki ikinci bolme acilinca ayni yerden gelsin.
        self._bolmeyi_sifirla(self.bolme)
        # q ile kapatilanlar, en yenisi sonda: {yol, sira, konum, zoom, sigdir}
        self.kapananlar: list[dict] = []
        self.ters: bool = bool(self.ayar["ters-renk"])
        # tex modu (T): acikken {yol, kodlama, ...}; editor parcalari ilk
        # acilista kurulur (bkz. _tex_arayuzu_kur)
        self.tex: dict | None = None
        self.tex_metin: tk.Text | None = None
        self.tex_karti: tk.Frame | None = None     # T'nin "yeni / ac" karti
        self._tex_karti_secili = 0
        self._boyut_isi = None             # pencere boyu durulunca yenile
        self._ipc_isi = None               # tek-pencere kuyruk yoklamasi
        # --- tepsi modu (bkz. _tepsi_kur) ---
        self._tepsi = None                 # (ileti penceresi, simge verisi)
        self._tepsi_kuyruk: list = []      # simgeye tiklamalar: "sol" | "sag"
        self._tepsi_isi = None
        self._tepsi_menu = None
        self._tamamen_cik: bool = False    # tepsi modunda da gercekten cik
        self._ikon_yolu: str = ""
        self._son_olcu: tuple[int, int] | None = None
        # Pencerenin buyutulmemis olcusu (en, boy, x, y) - kapanista bu yazilir,
        # bkz. _konumu_hatirla. `_acilis_buyuk`: kayit "buyutulmus" diyorsa
        # arayuz kurulduktan sonra zoomed'a gecilir.
        self._normal_konum: tuple[int, int, int, int] | None = None
        self._acilis_buyuk: bool = False

        # --- kip / girdi durumu ---
        self.mod: str = "normal"           # normal | komut | arama | icindekiler
        self.sayac: str = ""
        self.bekleyen: str | None = None   # g, isaret-koy, isarete-git
        self.gecici_ileti: str = ""
        self._ileti_rengi: str = self.ayar["cubuk-on"]
        self._baslik: str | None = None    # pencere basligi ve durum cubugu
        self._durum_yazili: tuple | None = None   # yalnizca degisince yazilir

        # --- eylem paleti ---
        self.palet_kip: str = "liste"      # liste | eylem | kaldir | yakala | onay
        self.palet_satirlar: list = []     # liste satiri -> komut (grup basligi None)
        self.palet_secim: int = 0
        self.palet_hedef: str = ""         # tus atanan komut
        self.palet_yeni_tus: str = ""
        self.alt_ogeleri: list[str] = []   # alt menudeki secenekler
        self.alt_secim: int = 0
        self._palet_en: int = 96           # liste satirinin karakter genisligi

        self.panel_konumlari: list = []    # vurgu / yer imi / belge listesinde satir -> oge

        # --- baglanti gosterimi (<C-l>) ve tiklama ---
        self._baglanti_iletisi: str = ""              # durum cubugundaki hedef ozeti

        # --- yazdirma: suren is (bkz. yazdir) ---
        self._baski: dict | None = None

        self.komutlar = self._komut_tablosu()
        self._duzen = None              # sayfa duzeni (S) acikken durumu
        self._karart_isi = None         # suren :karart taramasi
        self._arayuzu_kur()
        self._baglantilari_kur()
        self._ust_bari_yerlestir()
        self.cerceveyi_uygula()
        self._konumu_kesinlestir()
        if self._acilis_buyuk:      # gecen sefer buyutulmus kapatilmis
            self.state("zoomed")
            self.ust_dugmeler["buyut"].config(text="[=]")

        if self.yapi.hatalar:
            self.bildir(" | ".join(self.yapi.hata_metinleri()[:2]), "uyari")

        if isinstance(acilacak, str):
            acilacak = [acilacak]
        _pymupdf_bekle()                # pencere bu arada cizildi (cerceveyi_uygula)
        self.oturumu_yukle(acilacak or [])
        self._ipc_kur()
        if self.ayar["tepsi"]:
            self._tepsi_kur()

    # -- tek pencere: sonraki kopyalardan gelen dosyalar -------------------

    def _ipc_kur(self) -> None:
        """Ileti penceresini kurar ve kuyrugu yoklamaya baslar.

        Yoklama (150 ms) WM_COPYDATA yordamindan Tcl'e dokunmamak icin:
        yordam Tk'nin ileti dongusunun icinden cagriliyor, oradan Tk'ye is
        yaptirmak yerine listeye birakip burada isliyoruz.
        """
        if not self.ayar["tek-pencere"] or _ipc_penceresi():
            return                      # kapali ya da baska kopya zaten dinliyor
        self._ipc_kuyruk: list = []
        if _ipc_dinle(self._ipc_kuyruk):
            self._ipc_isi = self.after(150, self._ipc_yokla)

    def _ipc_yokla(self) -> None:
        while self._ipc_kuyruk:
            yollar = self._ipc_kuyruk.pop(0)
            self._arkadakileri_ekle(yollar[:-1])
            # Zaten bakilan belge yeniden yuklenmez (tepsiden donuste en sik
            # durum bu; 1612 sayfalik kitapta bastan acmak ~150 ms).
            if yollar and not (self.pdf_yolu and self._ayni_yol(yollar[-1], self.pdf_yolu)):
                self.belgeyi_ac(yollar[-1])
            self._one_gel()
        # Tepside gizliyken gelen PDF beklemesin: 15 ms (gorunurken 150 yeter)
        self._ipc_isi = self.after(15 if self._tepside() else 150, self._ipc_yokla)

    def _one_gel(self) -> None:
        """Simge durumundaysa aç, one getir. Dosya hangi pencereye gittiyse
        kullanici onu gorsun diye."""
        try:
            if self.state() in ("iconic", "withdrawn"):     # withdrawn: tepsiden
                self.deiconify()
            self.lift()
            self.focus_force()
            self.tuval.focus_set()
        except tk.TclError:
            pass

    # -- tepsi modu (Ctrl-K > ayarlar > tepsi) ------------------------------
    #
    # Kullanici "ilk acista yavas, sonra cok hizli" dedi: sicak acilis ~0,25 sn,
    # ama rubric uzun sure kapali kaldiginda ya da bilgisayar yeni acildiginda
    # Python, Tk ve ~30 MB'lik MuPDF diskten (ve Defender'dan) yeniden geciyor.
    # Tepsi modunda rubric hic kapanmaz, sogumaz: kapatinca (pencere X'i, Q)
    # konumlar ve oturum yazilir, pencere gizlenir, saatin yanina simge konur.
    # Simgeye sol tik ya da yeniden acmak (kisayol, "Birlikte ac" -> tek-pencere
    # yolu) pencereyi oldugu gibi geri getirir. Gercekten cikmak: sag tik > cik.
    # Kullanici kendisi acar (varsayilan kapali); Windows'la kendiliginden
    # baslamaz - istemedi.

    def tepsi_degistir(self) -> None:
        acik = not self.ayar["tepsi"]
        self.ayar["tepsi"] = acik
        if acik:
            self._tepsi_kur()
        else:
            self._tepsi_kaldir()
        self._kalici_bildir(self.m("tepsi_durum", durum=self.m("acik" if acik else "kapali")),
                            self.rc_tus_yaz({}, ayarlar={"tepsi": "true" if acik else "false"}))

    def _tepsi_kur(self) -> None:
        if sys.platform != "win32" or self._tepsi:
            return
        self._tepsi = _tepsi_simgesi(self._tepsi_kuyruk, self._ikon_yolu, "rubric")
        if self._tepsi and self._tepsi_isi is None:
            self._tepsi_isi = self.after(100, self._tepsi_yokla)

    def _tepsi_kaldir(self) -> None:
        if self._tepsi_isi is not None:
            self.after_cancel(self._tepsi_isi)
            self._tepsi_isi = None
        _tepsi_simgesini_kaldir(self._tepsi)
        self._tepsi = None

    def _tepside(self) -> bool:
        try:
            return self.state() == "withdrawn"
        except tk.TclError:
            return False

    def _tepsi_yokla(self) -> None:
        while self._tepsi_kuyruk:
            if self._tepsi_kuyruk.pop(0) == "sol":
                self._one_gel()
            else:
                self._tepsi_menusunu_ac()
        self._tepsi_isi = self.after(15 if self._tepside() else 100, self._tepsi_yokla)

    def _tepsi_menusunu_ac(self) -> None:
        """Sag tik: ac / cik. Tk'nin kendi (Windows'ta yerel) acilir menusu."""
        if self._tepsi_menu is None:
            self._tepsi_menu = tk.Menu(self, tearoff=0)
        menu = self._tepsi_menu
        menu.delete(0, "end")
        menu.add_command(label=self.m("tepsi_ac"), command=self._one_gel)
        menu.add_separator()
        menu.add_command(label=self.m("tepsi_cik"), command=self.tamamen_cik)
        x, y = self.winfo_pointerxy()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _tepsiye_in(self) -> None:
        """Tepsi modunda kapatma: her sey yazilir, pencere gizlenir; belge,
        bolmeler, konum oldugu gibi bellekte kalir."""
        for b in self.bolmeler:
            with self._bolmede(b):
                self._bekleyen_zoomu_birak()
                self.konumu_kaydet()
        self.oturumu_kaydet()
        self.withdraw()

    def tamamen_cik(self) -> None:
        self._tamamen_cik = True
        self.cik()

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
        if not self.yapi.ata("dil", dil):
            self.bildir(self.yapi.hata_metinleri()[-1], "hata")
            return
        yazildi = self.rc_tus_yaz({}, ayarlar={"dil": self.ayar["dil"]})
        self.metinleri_tazele()
        self._kalici_bildir(self.m("dil_secildi"), yazildi)

    def tema_uygula(self, tema: str) -> None:
        """Temayi uygular ve rubricrc'ye `set tema` olarak kalici yazar.
        rubricrc'de elle yazilmis tek tek renkler temanin ustunde kalir."""
        if tema not in TEMALAR:
            self.bildir(self.m("bilinmeyen_tema", ad=tema, secenekler=" ".join(TEMALAR)),
                        "hata")
            return
        self.yapi.ata("tema", tema)
        self.ayarlar_degisti(gorunumu_koru=True)    # o an acilmis gece modu / cift sayfa kalsin
        self._kalici_bildir(self.m("tema_secildi", ad=self.ad(f"tema-{tema}")),
                            self.rc_tus_yaz({}, ayarlar={"tema": tema}))

    def _kalici_bildir(self, ileti: str, yazildi: bool) -> None:
        """rubricrc'ye yazilan bir degisikligin iletisi; yazilamadiysa soyler."""
        self.bildir(ileti + ("" if yazildi else self.m("rc_yazilamadi_ek")),
                    "vurgu" if yazildi else "hata")

    def metinleri_tazele(self) -> None:
        """Dil degisince hazir duran (bir kez yazilip birakilan) metinler."""
        self.palet_alt_sol.config(text=self.m("palet_istem"))
        if self.mod == "palet":
            if self.palet_kip in ("yakala", "onay"):
                self.yakala_goster()
            elif self.palet_kip in ("renk-yakala", "renk-onay"):
                self.renk_yakala_goster()
            elif self.palet_kip in ("eylem", "kaldir"):
                self.alt_menuyu_kapat()
            self._paleti_yeniden_doldur()
        self.durumu_tazele()

    # -- arayuz ------------------------------------------------------------

    def _arayuzu_kur(self) -> None:
        """Pencerenin parcalari. Renk ve yazitipi burada verilmez, hepsi
        _renkleri_uygula()'da: acilista da :set / tema degisiminde de o calisir."""
        self.title("rubric")
        # exe'de ikon paketin icinden (_MEIPASS), betikte dosyanin yanindan gelir
        ikon = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                            "rubric.ico")
        if os.path.exists(ikon):
            self._ikon_yolu = ikon          # tepsi simgesi de bunu kullanir
            try:
                self.iconbitmap(default=ikon)
            except tk.TclError:
                pass
        self._pencereyi_konumla()

        # Tuvaller bir kapta yan yana durur (bkz. "bolmeler"); tek bolmede kap
        # da tek tuvali tasir, gorunum degismez.
        self.tuval_alani = tk.Frame(self, bd=0)
        self.tuval_alani.pack(side="top", fill="both", expand=True)
        self.bolme_cizgi = tk.Frame(self.tuval_alani, width=1, bd=0)   # tam 1 px ayirici
        self._tuval_kur(self.bolme)
        self._bolmeleri_yerlestir()

        # Ust bar: Windows baslik cubugunun yerine, temaya uygun. "$ rubric" istemi,
        # dosya adi ve ASCII pencere dugmeleri. Suruklenir, cift tik buyutur,
        # ust kenarindan boyutlandirilir. Gorunurlugu `baslik-cubugu` ayari.
        self.ust_bar = tk.Frame(self, bd=0)
        self.ust_cizgi = tk.Frame(self.ust_bar, height=1, bd=0)
        self.ust_cizgi.pack(side="bottom", fill="x")
        self.ust_dugmeler: dict[str, tk.Label] = {}
        for ad, metin in (("kapat", "[x]"), ("buyut", "[+]"), ("kucult", "[-]")):
            d = tk.Label(self.ust_bar, text=metin, bd=0, padx=5, pady=3)
            d.pack(side="right")
            d.bind("<Enter>", lambda e, ad=ad: self._dugme_uzerinde(ad, True))
            d.bind("<Leave>", lambda e, ad=ad: self._dugme_uzerinde(ad, False))
            d.bind("<ButtonRelease-1>", lambda e, ad=ad: self._dugme_tiklandi(e, ad))
            self.ust_dugmeler[ad] = d
        self.ust_istem = tk.Label(self.ust_bar, text="$ rubric", bd=0, padx=8, pady=3)
        self.ust_istem.pack(side="left")
        self.ust_ad = tk.Label(self.ust_bar, text="", anchor="w", bd=0, pady=3)
        self.ust_ad.pack(side="left", fill="x", expand=True)
        self._ust_ad_ham = ""

        # Durum cubugu: kose yuvarlatma yok, tek satir, monospace.
        self.cubuk = tk.Frame(self, bd=0)
        self.cubuk.pack(side="bottom", fill="x")
        self.durum = tk.Label(self.cubuk, text="", anchor="w", bd=0, padx=8, pady=2)
        self.durum.pack(side="left", fill="x", expand=True)
        self.sag_durum = tk.Label(self.cubuk, text="", anchor="e", bd=0, padx=8, pady=2)
        self.sag_durum.pack(side="right")

        # Komut / arama satiri; normalde gizli, ':' veya '/' ile acilir.
        self.komut_girdi = tk.Entry(self, bd=0, highlightthickness=0, insertwidth=8)

        # Icindekiler / vurgu / belge paneli (ayni liste)
        self.panel = tk.Frame(self, bd=0)
        # exportselection kapali: baska bir widget secim yapinca Tk bu listenin
        # secimini sessizce siliyor (palet listelerinde yasandi).
        self.liste = tk.Listbox(self.panel, bd=0, highlightthickness=0, activestyle="none",
                                exportselection=False)
        self.liste.pack(fill="both", expand=True)
        self.icindekiler_verisi: list[int] = []
        # Enter'la gidilen baslik: (satir, gidildikten sonraki aktif sayfa)
        self._icindekiler_hatira: tuple[int, int] | None = None

        self._paleti_kur()
        self._renkleri_uygula()

    def _paleti_kur(self) -> None:
        """Eylem paleti: ortada duran, uzerine binen bir kart.

        Raycast'teki duzen: ustte arama satiri, ortada komutlar ve o anki
        tuslari, sag altta secili komutun eylemleri.
        """
        self.palet = tk.Frame(self, bd=0, highlightthickness=1)

        self.palet_ust = tk.Frame(self.palet)
        self.palet_ust.pack(side="top", fill="x")
        self.palet_onek = tk.Label(self.palet_ust, text=">", bd=0, padx=9, pady=7)
        self.palet_onek.pack(side="left")
        self.palet_desen = tk.StringVar()
        self.palet_girdi = tk.Entry(self.palet_ust, textvariable=self.palet_desen, bd=0,
                                    highlightthickness=0, insertwidth=8)
        self.palet_girdi.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.palet_cizgi_ust = tk.Frame(self.palet, height=1)
        self.palet_cizgi_ust.pack(side="top", fill="x")

        # Alt ipucu cubugu once paketlenir; dar pencerede listeyi o kirpsin.
        self.palet_alt = tk.Frame(self.palet)
        self.palet_alt.pack(side="bottom", fill="x")
        self.palet_alt_sol = tk.Label(self.palet_alt, text=self.m("palet_istem"), bd=0,
                                      padx=9, pady=3)
        self.palet_alt_sol.pack(side="left")
        self.palet_ipucu = tk.Label(self.palet_alt, text="", anchor="e", bd=0, padx=9, pady=3)
        self.palet_ipucu.pack(side="right")

        self.palet_liste = tk.Listbox(self.palet, bd=0, highlightthickness=0, activestyle="none",
                                      takefocus=False, exportselection=False)
        self.palet_liste.pack(side="top", fill="both", expand=True)

        # Sag alttaki eylem menusu (ve "hangi tusu kaldirayim" listesi).
        self.alt_menu = tk.Frame(self.palet, bd=0, highlightthickness=1)
        self.alt_baslik = tk.Label(self.alt_menu, text="", anchor="w", bd=0, padx=8, pady=4)
        self.alt_baslik.pack(side="top", fill="x")
        # exportselection kapali: iki listbox ayni anda seciliyken Tk digerinin
        # secimini sessizce siliyor (alt menu acilinca ana liste sonuyordu).
        self.alt_liste = tk.Listbox(self.alt_menu, bd=0, highlightthickness=0, activestyle="none",
                                    takefocus=False, exportselection=False)
        self.alt_liste.pack(side="top", fill="both", expand=True, pady=(0, 4))

        # Tus yakalama / onay ekrani - paletin ortasinda durur.
        self.yakala = tk.Frame(self.palet, bd=0, padx=22, pady=16, highlightthickness=1)
        self.yakala_ust = tk.Label(self.yakala, text="")
        self.yakala_ust.pack(side="top", pady=(0, 6))
        self.yakala_orta = tk.Label(self.yakala, text="")
        self.yakala_orta.pack(side="top")
        self.yakala_alt = tk.Label(self.yakala, text="")
        self.yakala_alt.pack(side="top", pady=(8, 0))

    def _renkleri_uygula(self) -> None:
        """Butun parcalarin renk ve yazitipi, tek yerde."""
        a = self.ayar
        yt, buyuk = (a["yazitipi"], a["yazitipi-boy"]), (a["yazitipi"], a["yazitipi-boy"] + 3)
        cubuk, panel, palet, secili = (a["cubuk-zemin"], a["panel-zemin"], a["palet-zemin"],
                                       a["panel-secili"])
        liste = {"fg": a["cubuk-on"], "selectbackground": secili,
                 "selectforeground": a["vurgu"], "font": yt}
        for w, secenek in (
            (self, {"bg": a["zemin"]}),
            (self.tuval_alani, {"bg": a["zemin"]}),     # tuvaller: _bolmeleri_boya
            (self.ust_bar, {"bg": cubuk}),
            (self.ust_cizgi, {"bg": a["palet-cerceve"]}),
            (self.ust_istem, {"bg": cubuk, "fg": a["vurgu"], "font": yt}),
            (self.ust_ad, {"bg": cubuk, "fg": a["cubuk-on"], "font": yt}),
            *((d, {"bg": cubuk, "fg": a["sonuk"], "font": yt}) for d in self.ust_dugmeler.values()),
            (self.cubuk, {"bg": cubuk}),
            (self.durum, {"bg": cubuk, "font": yt}),                  # fg durumu_tazele'de
            (self.sag_durum, {"bg": cubuk, "fg": a["vurgu"], "font": yt}),
            (self.komut_girdi, {"bg": cubuk, "fg": a["vurgu"], "insertbackground": a["vurgu"],
                                "font": yt}),
            (self.panel, {"bg": panel}),
            (self.liste, {"bg": panel, **liste}),
            (self.palet, {"bg": palet, "highlightbackground": a["palet-cerceve"]}),
            (self.palet_ust, {"bg": palet}),
            (self.palet_onek, {"bg": palet, "fg": a["vurgu"], "font": buyuk}),
            (self.palet_girdi, {"bg": palet, "fg": a["cubuk-on"], "insertbackground": a["vurgu"],
                                "font": buyuk}),
            (self.palet_cizgi_ust, {"bg": a["palet-cerceve"]}),
            (self.palet_alt, {"bg": cubuk}),
            (self.palet_alt_sol, {"bg": cubuk, "fg": a["sonuk"], "font": yt}),
            (self.palet_ipucu, {"bg": cubuk, "fg": a["cubuk-on"], "font": yt}),
            (self.palet_liste, {"bg": palet, **liste}),
            (self.alt_menu, {"bg": panel, "highlightbackground": a["palet-cerceve"]}),
            (self.alt_baslik, {"bg": panel, "fg": a["sonuk"], "font": yt}),
            (self.alt_liste, {"bg": panel, **liste}),
            (self.yakala, {"bg": secili, "highlightbackground": a["vurgu"]}),
            (self.yakala_ust, {"bg": secili, "fg": a["vurgu"], "font": buyuk}),
            (self.yakala_orta, {"bg": secili, "font": yt}),           # fg yakala_goster'de
            (self.yakala_alt, {"bg": secili, "fg": a["sonuk"], "font": yt}),
        ):
            w.config(**secenek)
        self._bolmeleri_boya()
        if self.tex_metin is not None:
            self._tex_renkleri()
        self._durum_yazili = None          # durum satiri yeni renkle yeniden yazilsin

    def _tuval_baglari(self, bolme: Bolme) -> None:
        """Bir bolmenin tuvalindeki fare olaylari.

        Imlec bir bolmenin uzerine girdiginde orasi **etkin** olur
        (`fareyle_bolmeye_gec`), tik de oyle. Ayar kapaliysa ya da gecise
        uygun an degilse olay yine de dogru bolmede yurur (`orada`): imleci
        bakilmayan bolmeye goturup tekerlegi cevirmek onu kaydirir, orada bir
        baglantinin hedefi durum cubugunda gorunur.
        """
        t = bolme.tuval

        def gec(islev):                     # tik: o bolme etkin olur
            def sarmal(olay, b=bolme):
                self._bolmeye_gec(b)
                return islev(olay)
            return sarmal

        def orada(islev):                   # o bolmede yurut (gecis olmasa da)
            def sarmal(olay, b=bolme):
                with self._bolmede(b):
                    return islev(olay)
            return sarmal

        def fareyle(islev):                 # imlec girdi / gezindi: taban bu bolme
            def sarmal(olay, b=bolme):
                self.fareyle_bolmeye_gec(b)
                with self._bolmede(b):
                    return islev(olay)
            return sarmal

        t.bind("<Enter>", fareyle(lambda e: None))
        t.bind("<MouseWheel>", fareyle(self.tekerlek))
        t.bind("<Control-MouseWheel>", fareyle(self.ctrl_tekerlek))
        t.bind("<Button-1>", gec(lambda e: self.tuval.focus_set()))
        # Tab'i tuval kendi sinif baglantisiyla odak gezmeye cevirir; once biz
        # yakalayip kesmezsek <Tab> hicbir zaman icindekilere ulasmaz.
        t.bind("<Tab>", self.tab_geldi)
        t.bind("<Shift-Tab>", self.tab_geldi)
        # Sol tus: kalem acik ya da Shift basiliysa metin vurgular, degilse
        # sayfayi tutup kaydirir (fare_bas karar verir). Sag tik vurguyu siler.
        t.bind("<B1-Motion>", orada(self.fare_surukle))
        t.bind("<ButtonPress-1>", gec(self.fare_bas))
        t.bind("<ButtonRelease-1>", orada(self.fare_birak))
        # Bos gezinme: taban bu bolme olur + baglantinin ustunde el imleci
        t.bind("<Motion>", fareyle(self._gezinme))
        t.bind("<Leave>", orada(self._baglantidan_cik))
        t.bind("<Button-3>", gec(self.sag_tik))

    def _baglantilari_kur(self) -> None:
        self.bind("<Key>", self.tus_geldi)
        self.bind("<Configure>", self.pencere_degisti)
        self.komut_girdi.bind("<Return>", self.komut_onayla)
        self.komut_girdi.bind("<Escape>", lambda e: self.komut_iptal())
        self.liste.bind("<Key>", self.panel_tus)
        self.liste.bind("<Double-Button-1>", lambda e: self.panel_sec())
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
        if yol.lower().endswith(".tex"):          # kaynak: yaninda PDF'iyle tex modu
            self.tex_ac(yol)
            return
        if not os.path.exists(yol):
            self.bildir(self.m("bulunamadi", ne=yol), "hata")
            return
        try:
            yeni = pymupdf.open(yol)
        except Exception as e:
            self.bildir(self.m("acilamadi", e=e), "hata")
            return

        if self.mod == "sayfa-duzeni":     # kucuk resimler eski belgeye bakiyor
            self._duzeni_kapat()
        if self.belge is not None:
            self.konumu_kaydet()
            self.belge.close()

        self.belge = yeni
        self.pdf_yolu = yol
        self._olcu = {}
        self._icindekiler_hatira = None
        self._bekleyen_zoomu_birak()
        self.onbellek.clear()
        self._tuvali_temizle()
        self._aramayi_birak()           # onceki belgenin taramasi surmesin
        self.zipla_gecmis, self.zipla_ileri = [], []

        kayit = self.kalici.dosya(yol)
        self.isaretler = {k: tuple(v) for k, v in kayit.get("isaretler", {}).items()
                          if isinstance(v, (list, tuple)) and len(v) == 2}
        self._secim = None
        self._bekleyen_vurgu = None
        self.karartmalar = []
        self._karartma_cizimi = None
        self._kelimeler = {}
        self._baglantilar = {}
        self._satir_metinleri = {}
        self._capa = None
        self._baglanti_cizili = False
        self._baglanti_adayi = None
        self._imlecteki_baglanti = None
        self.vurgu_gecmisi = []
        self._vurgulari_yukle(kayit)
        self._imlecteki_not = None
        self._duzenlenen_not = None
        self.geri_yigini = []
        self._notlari_yukle(kayit)

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

    # -- bolmeler (sol / sag) ----------------------------------------------
    #
    # Sema:
    #   <A-Right>  bakilan belgeyi SAG bolmeye at   (bolme yoksa acilir)
    #   <A-Left>   bakilan belgeyi SOL bolmeye at
    #   <A-w>      oteki bolmeye gec
    #   <A-o>      tek bolmeye don (otekinin belgeleri bu listeye katilir)
    #
    # Attiktan sonra odak: kaynak bolmede baska belge kaldiysa **atilan
    # belgeye** gider (attigini gorursun); kaynak bos kaldiysa **bos bolmede**
    # kalir, boylece `o` ile ikinci belge oraya acilir. Bir belgeyle baslayan
    # "birini saga, otekini sola" akisi tam boyle yuruyor.
    #
    # Kapanis: `q` once o bolmenin kendi listesini tuketir (sagda iki belge
    # varsa ilk q yalnizca otekine gecer); bolmenin son belgesi de kapaninca
    # bolme kapanir ve odak oteki bolmeye gecer. Tek bolme kalmissa eskisi
    # gibi bos ekran olur, cikmak icin Q. <C-e> kapanani bolmesiyle geri acar.

    @property
    def bolme(self) -> Bolme:
        return self.bolmeler[self.etkin]

    def _bolmeyi_sifirla(self, bolme: Bolme) -> None:
        """Bir bolmenin butun belge / gorunum durumu, bos halinde.

        Hem acilistaki ilk bolme hem sonradan acilan ikinci bolme buradan
        gelir; yoksa ikincisi None dolu dogar.
        """
        with self._bolmede(bolme):
            self.belge = None
            self.pdf_yolu = ""
            # Bu bolmenin belge listesi (<C-Left>/<C-Right>). Yalnizca yollar:
            # bellekte bolme basina tek belge acik, gerisinin kaldigi yer
            # durum.json'da. Liste oturumda `_oturum.bolmeler` altinda saklanir.
            self.belgeler = []
            self.zoom = 1.0
            self.donme = 0
            self.sigdir = self.ayar["sigdir"]
            self.sutunlar = max(1, int(self.ayar["sutunlar"]))

            # duzen
            self.satirlar = []          # her satir bir sayfa grubu
            self.yerler = []            # sayfa no -> tuvaldeki yeri (satirlardakiyle ayni dict)
            self._altlar = []           # satirlarin alt kenari; gorunen satiri bisect bulur
            self.toplam_yukseklik = 0
            self.toplam_genislik = 0
            self._olcu = {}             # sayfa -> donmesiz siniri (pt)
            # yakinlastirma: olaylar hedefi gunceller, cizim bosta bir kez yapilir
            self._hedef_zoom = None
            self._zoom_ekran = (0.0, 0.0)
            self._zoom_isi = None
            self._komsu_isi = None
            self.onbellek = collections.OrderedDict()
            self.tuval_ogeleri = {}
            self.aktif_sayfa = 0

            # arama
            self.bulgular = []
            self.bulgu_no = -1
            self.son_desen = ""
            self.arama_yonu = 1
            self.arama_kuyrugu = []
            self.arama_kimlik = 0       # yeni arama eskisini gecersiz kilar
            self._aktif_bulgu = None
            self._ilk_atlama = False

            # ziplama listesi / isaretler: konum_imi() ikilileri
            self.zipla_gecmis = []
            self.zipla_ileri = []
            self.isaretler = {}

            # metin vurgulari (highlight)
            self.vurgular = []          # durum.json'daki kayitlarin kendisi
            self._vurgu_xref = {}       # vurgu kimligi -> bellekteki not
            self.vurgu_gecmisi = []     # u ile geri alma
            self.kalem = False          # vurgu kalemi acik mi (v)
            self.silme_kipi = False     # silme kipi acik mi (<Delete>)
            self._secim = None          # suren surukleme secimi
            self._kelimeler = {}        # sayfa -> kelime kutulari
            # Birakilan secim renk bekler: Enter varsayilan, renk tusu o renk, Esc birakir.
            self._bekleyen_vurgu = None

            # karartma (X): yeni dosyaya yazilana kadar yalnizca bellekte
            self.karartma_acik = False
            self.karartmalar = []       # {sayfa, dik}
            self._karartma_cizimi = None  # suren kutu surukleme

            # kenar notlari (i)
            self.notlar = []            # durum.json'daki kayitlarin kendisi
            self._imlecteki_not = None  # balonu acik olan not
            self._duzenlenen_not = None # komut satirinda yazilan not
            self.geri_yigini = []       # U ile geri alma

            # baglanti gosterimi (<C-l>) ve tiklama
            self.baglantilar_acik = False
            self._baglantilar = {}      # sayfa -> [(dikdortgen, kayit)]
            self._baglanti_cizili = False
            self._imlecteki_baglanti = None   # el imlecini bir kez degistirmek icin
            self._baglanti_adayi = None       # basilan baglanti (birakinca acilir)
            self._basis_noktasi = None        # sol tusun basildigi ekran noktasi
            self._surukleniyor = False
            # "su sayfa" diyen baglantinin capasi (bkz. baglanti_capasi)
            self._satir_metinleri = {}
            self._capa = None
            self._capa_isi = None

            self._icindekiler_hatira = None

    def _bolme_yarat(self, sag: bool) -> Bolme:
        """Yeni bolmeyi istenen yana koyar, durumunu sifirlar, tuvalini kurar.
        Bakilan bolme yerinde kalir; solda acilinca indisi bir kayar."""
        yeni = Bolme()
        if sag:
            self.bolmeler.append(yeni)
        else:
            self.bolmeler.insert(0, yeni)
            self.etkin += 1
        self._bolmeyi_sifirla(yeni)
        self._tuval_kur(yeni)
        return yeni

    def bolundu(self) -> bool:
        return len(self.bolmeler) > 1

    @contextlib.contextmanager
    def _bolmede(self, bolme: Bolme):
        """Etkin bolmeyi gecici degistirir: bakilmayan bolmeyi cizmek,
        olcmek, kapatmak icin. Odaga ve boyamaya dokunmaz."""
        eski = self.etkin
        try:
            self.etkin = self.bolmeler.index(bolme)
        except ValueError:
            yield
            return
        try:
            yield
        finally:
            self.etkin = min(eski, len(self.bolmeler) - 1)

    def _tuval_kur(self, bolme: Bolme) -> None:
        """Bolmenin cercevesi ve tuvali. Cerceve 1 px: etkin bolme vurgu
        renginde cerceveli olur (tam sayi piksel, kesirli kenar yok)."""
        bolme.cerceve = tk.Frame(self.tuval_alani, bd=0, highlightthickness=1)
        bolme.tuval = tk.Canvas(bolme.cerceve, highlightthickness=0, bd=0, takefocus=True)
        bolme.tuval.pack(fill="both", expand=True)
        self._tuval_baglari(bolme)

    def _bolmeleri_yerlestir(self) -> None:
        for b in self.bolmeler:
            b.cerceve.pack_forget()
        self.bolme_cizgi.pack_forget()
        if self.tex_metin is not None:
            self.tex_cerceve.pack_forget()
            self.tex_cizgi.pack_forget()
        if self.tex:
            # Editor once yerlesir, sabit genislikte; bolmeler kalani paylasir.
            yan = "right" if str(self.ayar["tex-yan"]).strip().lower() in ("sag", "sağ", "right") \
                else "left"
            self.tex_cerceve.config(width=self._tex_genisligi())
            self.tex_cerceve.pack(side=yan, fill="y")
            self.tex_cizgi.pack(side=yan, fill="y")
        for i, b in enumerate(self.bolmeler):
            if i:
                self.bolme_cizgi.pack(side="left", fill="y")
            b.cerceve.pack(side="left", fill="both", expand=True)
        self._bolmeleri_boya()
        # Tuvallerin yeni genisligi **simdi** olculsun: bundan sonra cagrilan
        # yenile / duzeni_hesapla `tuval.winfo_width()` okuyor ve Tk geometriyi
        # bosta hesapladigi icin eski genisligi veriyordu. Bolme kapaninca
        # kalan tuval tam genislikteydi ama duzen yarim genisliktendi: ekranin
        # yarisi bos kaliyordu, ancak <C-Right> gibi belgeyi yeniden acan bir
        # komuttan sonra duzeliyordu.
        self.update_idletasks()

    def _bolmeleri_boya(self) -> None:
        a = self.ayar
        self.bolme_cizgi.config(bg=a["palet-cerceve"])
        bolundu = self.bolundu()
        for b in self.bolmeler:
            kenar = (a["vurgu"] if b is self.bolme else a["palet-cerceve"]) if bolundu \
                else a["zemin"]
            # Tek bolmede cerceve hic yok (kalinlik 0): tuval eskisi gibi tam
            # tepeden basliyor, 1 px kaymiyor. Bolununce 1 px - tam sayi.
            b.cerceve.config(bg=a["zemin"], highlightthickness=1 if bolundu else 0,
                             highlightbackground=kenar, highlightcolor=kenar)
            b.tuval.config(bg=a["zemin"])

    def _bolmeye_gec(self, bolme: Bolme, diske: bool = True) -> None:
        if bolme is self.bolme or bolme not in self.bolmeler:
            return
        if self.mod in ("icindekiler", "vurgular", "belgeler", "yer-imleri"):
            self.paneli_kapat()                  # panel ayrildigi belgenindi
        self.konumu_kaydet(diske)
        self.etkin = self.bolmeler.index(bolme)
        self._bolmeleri_boya()
        self.tuval.focus_set()
        self._durum_yazili = None
        self.durumu_tazele()

    def fareyle_bolmeye_gec(self, bolme: Bolme) -> None:
        """Fare bir bolmenin uzerine girince orasi etkin olur (`fare-bolme`).

        Sag belgenin tablosuna gidip `j`'ye basan sagi kaydirsin, tekerlek de
        sagi cevirsin diye: imlecin durdugu bolme "taban" sayilir.

        Gecmedigi haller - hepsi de gecerse fare kazayla is bozardi:
        - `fare-bolme false` (ayar kapali);
        - normal kip disi: panel, palet, komut satiri acikken odak oradadir,
          fare gezindi diye kapanmamali;
        - suren surukleme / metin secimi / renk bekleyen vurgu: is bakilan
          bolmede basladi, ortasinda taban degismemeli;
        - `g` gibi bekleyen iki tuslu dizi ya da sayi oneki varken.
        """
        if bolme is self.bolme or not self.ayar["fare-bolme"]:
            return
        if self.mod != "normal" or self.bekleyen or self.sayac:
            return
        if self._surukleniyor or self._secim is not None or self._bekleyen_vurgu is not None:
            return
        self._bolmeye_gec(bolme, diske=False)

    def _bolme_ac(self, sag: bool) -> Bolme:
        """Istenen yandaki bolmeyi verir; yoksa acar. Bakilan bolme yerinde
        kalir, yalnizca yeni bolme yanina girer."""
        if self.bolundu():
            return self.bolmeler[1 if sag else 0]
        yeni = self._bolme_yarat(sag)
        self._bolmeleri_yerlestir()              # yeni genislikleri de olcer
        return yeni

    def _bolmeyi_yik(self, bolme: Bolme) -> None:
        """Bolmeyi kapatir: belgesini kapatir, bekleyen islerini iptal eder,
        cercevesini yok eder. `etkin` kayan indislere gore duzeltilir."""
        if bolme not in self.bolmeler or not self.bolundu():
            return
        i = self.bolmeler.index(bolme)
        with self._bolmede(bolme):
            self._bekleyen_zoomu_birak()
            for isim in ("_komsu_isi", "_capa_isi"):
                if getattr(self, isim) is not None:
                    self.after_cancel(getattr(self, isim))
                    setattr(self, isim, None)
            self._aramayi_birak()
            if self.belge is not None:
                try:
                    self.belge.close()
                except Exception:
                    pass
                self.belge = None
        bolme.cerceve.destroy()
        del self.bolmeler[i]
        if self.etkin >= i:
            self.etkin = max(0, self.etkin - 1)
        self.etkin = min(self.etkin, len(self.bolmeler) - 1)
        self._bolmeleri_yerlestir()

    def _yan_adi(self, bolme: Bolme) -> str:
        return self.m("yan_sag" if self.bolmeler.index(bolme) else "yan_sol")

    def belgeyi_bolmeye(self, sag: bool) -> None:
        """<A-Right> / <A-Left>: bakilan belgeyi o yandaki bolmeye tasir."""
        if not self.belge:
            self.bildir(self.m("bolme_belge_yok"), "uyari")
            return
        if self.bolundu() and self.bolmeler[1 if sag else 0] is self.bolme:
            self.bildir(self.m("bolme_zaten", yan=self.m("yan_sag" if sag else "yan_sol")),
                        "uyari")
            return
        yol, kaynak = self.pdf_yolu, self.bolme
        self.konumu_kaydet()
        hedef = self._bolme_ac(sag)              # bolme yoksa acar (kaynak yerinde kalir)

        i = self._sira(yol)                      # kaynak listesinden dusur
        if i >= 0:
            del self.belgeler[i]
        kalan = self.belgeler[min(i, len(self.belgeler) - 1)] if self.belgeler else None
        if kalan:
            self.belgeyi_ac(kalan)
        else:
            self._belgeyi_birak()

        self.etkin = self.bolmeler.index(hedef)  # hedefe koy
        self._listeye_ekle(yol)
        self.belgeyi_ac(yol)
        if kalan is None:
            self.etkin = self.bolmeler.index(kaynak)   # bos bolmede kal: `o` orayi doldursun
        self._bolmeleri_boya()
        self.tuval.focus_set()
        self.yenile()
        self.oturumu_kaydet()
        self.bildir(self.m("bolmeye_tasindi", ad=os.path.basename(yol),
                           yan=self.m("yan_sag" if sag else "yan_sol")), "vurgu")

    def bolme_gec(self) -> None:
        """<A-w>: oteki bolmeye gec."""
        if not self.bolundu():
            self.bildir(self.m("bolme_yok"), "uyari")
            return
        self._bolmeye_gec(self.bolmeler[1 - self.etkin])
        self.bildir(self.m("bolmeye_gecildi", yan=self._yan_adi(self.bolme)), "vurgu")

    def bolme_tek(self) -> None:
        """<A-o>: tek bolmeye don. Otekinin belgeleri kaybolmaz, bu bolmenin
        listesine katilir (yalnizca gorunum kapanir)."""
        if not self.bolundu():
            self.bildir(self.m("bolme_yok"), "uyari")
            return
        oteki = self.bolmeler[1 - self.etkin]
        with self._bolmede(oteki):
            self.konumu_kaydet()
            tasinan = list(self.belgeler)
        self._bolmeyi_yik(oteki)
        for y in tasinan:
            self._listeye_ekle(y)
        self._listeyi_kirp()
        self._bolmeleri_boya()
        self.tuval.focus_set()
        self.yenile()
        self.oturumu_kaydet()
        self.bildir(self.m("bolme_kapandi", n=len(tasinan)), "vurgu")

    def _bolmeyi_kapat_ve_gec(self) -> None:
        """Bolmenin son belgesi de kapandi: bolme kapanir, odak otekine gecer."""
        self._bolmeyi_yik(self.bolme)
        self._bolmeleri_boya()
        self.tuval.focus_set()
        self.yenile()

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

    def _arkadakileri_ekle(self, yollar: list[str]) -> None:
        """Coklu dosya (komut satiri, dosya penceresi): sonuncusu disindakiler
        acilmadan listeye girer; sonuncusunu cagiran acar."""
        for y in yollar[:-1]:
            y = os.path.abspath(y)
            if os.path.exists(y):
                self.kalici.dosya(y)["goruldu"] = time.time()
                self._listeye_ekle(y)

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

    # -- pencerenin yeri ve boyu -------------------------------------------
    #
    # durum.json'da `_pencere` anahtari; belge kayitlari dosya yollarinda
    # durdugu icin alt tire ile baslayan ad onlarla cakismaz. `_oturum`'un
    # icine konmadi: pencerenin yeri hangi belgelerin acik oldugundan ayri
    # bir sey, `set oturum false` diyen de kendi boyunu geri istiyor.

    def _konumu_hatirla(self) -> None:
        """Pencerenin buyutulmemis olcusunu akilda tutar.

        Olcu Win32 cerceve dikdortgeninden okunur (bkz. _pencere_dikdortgeni);
        Tk'nin geometry()'si bu pencerede tam donus yapmiyor.

        Buyutulmusken olcu alinmaz: Windows o sirada ekranin boyunu verir,
        onu kaydedersek kucultme boyu bir daha geri gelmez. Tam ekran ve
        tepsiye inmis pencere de ayni sebeple atlanir; o anlarda son bilinen
        normal olcu korunur."""
        try:
            if self.state() != "normal" or self.attributes("-fullscreen"):
                return
            g = _pencere_dikdortgeni(self) or _geometriyi_coz(self.geometry())
        except tk.TclError:                 # yok edilmis pencere
            return
        if g and g[0] > 1 and g[1] > 1:     # daha cizilmemis pencere 1x1 der
            self._normal_konum = g

    def _pencere_kaydi(self) -> dict:
        self._konumu_hatirla()
        if not self._normal_konum:
            return {}
        en, boy, x, y = self._normal_konum
        try:
            buyuk = self.state() == "zoomed"
        except tk.TclError:
            buyuk = False
        return {"en": en, "boy": boy, "x": x, "y": y, "buyuk": buyuk}

    def _pencereyi_konumla(self) -> None:
        """Acilista pencereyi gecen seferki yerine ve boyuna koyar.

        Kayit ekran disina dusuyorsa (monitor cikarilmis, cozunurluk dusmus,
        pencere ikinci ekranda birakilmis) ic ekrana cekilir: yoksa rubric
        gorunmeyen bir kosede acilir ve kullanici penceresini bulamaz."""
        en, boy, x, y = 1000, 760, None, None
        p = self.kalici.veri.get("_pencere")
        if isinstance(p, dict):
            try:
                en, boy = max(480, int(p["en"])), max(360, int(p["boy"]))
                x, y = int(p["x"]), int(p["y"])
                self._acilis_buyuk = bool(p.get("buyuk"))
            except (KeyError, TypeError, ValueError):
                en, boy, x, y = 1000, 760, None, None
                self._acilis_buyuk = False
        if x is None:
            self.geometry(f"{en}x{boy}")    # ilk acilis: yerini Windows secsin
            return
        ex, ey, ege, eby = _ekran_alani(self)
        en, boy = min(en, ege), min(boy, eby)
        x = max(ex, min(x, ex + ege - en))
        y = max(ey, min(y, ey + eby - boy))
        self._normal_konum = (en, boy, x, y)    # buyuk acilirsa kucultme boyu bu
        # Yaklasik yerlestirme: pencere yanlis kosede bir an gorunmesin.
        # Kesini _konumu_kesinlestir yapar - pencere daha yaratilmadi.
        self.geometry(f"{en}x{boy}+{x}+{y}")

    def _konumu_kesinlestir(self) -> None:
        """Arayuz kurulduktan sonra pencereyi tam kaydedilen dikdortgene oturtur.

        Ayri adim, cunku _pencereyi_konumla widget'lar kurulurken calisiyor:
        pencerenin Win32 tutamaci daha yok, MoveWindow orada is gormez.

        Buyutulmus acilacaksa da once bu calisir: Windows'un "kucultunce
        nereye donecegi" pencerenin buyutulmeden onceki dikdortgenidir,
        onu koymazsak [+] tusuna basan kaydettigi boya degil Tk'nin
        yaklasik boyuna doner."""
        if self._normal_konum:
            _pencereyi_tasi(self, *self._normal_konum)

    def oturumu_kaydet(self) -> None:
        # kapananlar da yazilir: q'dan hemen sonra Q'ya basan geri acabilsin.
        # `belgeler` / `aktif` bakilan bolmenindir: eski bicimi okuyan (ve
        # bolme bilmeyen) bir surum de makul bir oturum bulur.
        self.kalici.veri["_oturum"] = {
            "belgeler": list(self.belgeler),
            "aktif": self.pdf_yolu,
            "kapananlar": list(self.kapananlar),
            "bolmeler": [{"belgeler": list(b.belgeler or []), "aktif": b.pdf_yolu or ""}
                         for b in self.bolmeler],
            "etkin": self.etkin,
        }
        kayit = self._pencere_kaydi()
        if kayit:                           # olcu alinamadiysa eskisini silme
            self.kalici.veri["_pencere"] = kayit
        self.kalici.yaz()

    def oturumu_yukle(self, acilacak: list[str]) -> None:
        """Acilis: onceki oturumun bolmeleri + komut satirindan gelenler.
        Komut satirinda dosya verildiyse o, verilmediyse en son bakilan acilir."""
        kayit = self.kalici.veri.get("_oturum") if self.ayar["oturum"] else None
        eksik, etkin = 0, 0
        gruplar: list[tuple[list[str], str]] = []
        if isinstance(kayit, dict):
            ham = kayit.get("bolmeler")
            if not isinstance(ham, list) or not ham:        # bolme bilmeyen eski kayit
                ham = [{"belgeler": kayit.get("belgeler", []), "aktif": kayit.get("aktif")}]
            for g in ham[:2]:
                if not isinstance(g, dict):
                    continue
                eski = [y for y in g.get("belgeler", []) if isinstance(y, str)]
                var = [y for y in eski if os.path.exists(y)]
                eksik += len(eski) - len(var)
                if var:                                     # bos bolme geri getirilmez
                    gruplar.append((var, g.get("aktif") or ""))
            self.kapananlar = [k for k in kayit.get("kapananlar", [])
                               if isinstance(k, dict) and isinstance(k.get("yol"), str)]
            self._kapananlari_kirp()
            try:
                etkin = max(0, min(int(kayit.get("etkin", 0)), len(gruplar) - 1))
            except (TypeError, ValueError):
                etkin = 0
        while len(self.bolmeler) < len(gruplar):            # ikinci bolmeyi geri kur
            self._bolme_yarat(True)
        if len(self.bolmeler) > 1:
            self._bolmeleri_yerlestir()

        # Her bolme kendi listesini ve kaldigi belgeyi geri alir; en son
        # bakilan bolme etkin kalir.
        for i, (yollar, aktif) in enumerate(gruplar):
            self.etkin = i
            self.belgeler = list(yollar)
            self.belgeyi_ac(aktif if (aktif and self._sira(aktif) >= 0) else yollar[-1])
        self.etkin = etkin if gruplar else 0

        # Komut satirindan / dosya penceresinden gelenler etkin bolmeye acilir.
        yeniler = [os.path.abspath(y.strip().strip('"')) for y in acilacak]
        if yeniler:
            self._arkadakileri_ekle(yeniler)
            self.belgeyi_ac(yeniler[-1])
        elif not self.belge:
            self.bildir(self.m("ipucu_bos"), "vurgu")
        self._bolmeleri_boya()
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
        bolme_kapandi = False
        if bakilan:
            if self.belgeler:
                # belgeyi_ac eskisinin konumunu da yazar; listede artik yok, sorun degil
                self.belgeyi_ac(self.belgeler[min(i, len(self.belgeler) - 1)])
            elif self.bolundu():
                # bolmenin son belgesi: bolme kapanir, odak otekine gecer
                self._bolmeyi_kapat_ve_gec()
                bolme_kapandi = True
            else:
                self._belgeyi_birak()
        self.oturumu_kaydet()
        if bolme_kapandi:
            self.bildir(self.m("bolme_belgesiz_kapandi", ad=os.path.basename(yol),
                               tus=self._geri_ac_tusu()), "vurgu")
            return
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
        # Hangi bolmedeydi: son belgesi kapaninca bolme de kapaniyor, <C-e>
        # onu da geri getirsin. Tek bolmede yan yok.
        if self.bolundu():
            giris["yan"] = "sag" if self.etkin else "sol"
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
        self._kalici_bildir(self.m("sinir_secildi", n=n),
                            self.rc_tus_yaz({}, ayarlar={"kapanan-belgeler": str(n)}))

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
        for b in self.bolmeler:                 # bu arada o ile yeniden acilmis: oraya gec
            with self._bolmede(b):
                acikti = self._sira(yol) >= 0
            if acikti:
                self._bolmeye_gec(b)
                self.belgeyi_ac(yol)
                return
        yan = k.get("yan")
        if yan in ("sol", "sag"):               # kapandigi bolmeye don, bolme kapandiysa geri ac
            hedef = self._bolme_ac(yan == "sag") if not self.bolundu() \
                else self.bolmeler[1 if yan == "sag" else 0]
            self.etkin = self.bolmeler.index(hedef)
            self._bolmeleri_boya()
            self.tuval.focus_set()
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
            self._tuvali_temizle()
            self.duzeni_hesapla()
        self.konum_imine_git(k.get("konum"))
        self.konumu_kaydet()
        self.oturumu_kaydet()
        ad = os.path.basename(yol)
        self.bildir(self.m("geri_acildi_daha", ad=ad, n=len(self.kapananlar))
                    if self.kapananlar else self.m("geri_acildi", ad=ad), "vurgu")

    def _belgeyi_birak(self) -> None:
        """Hic belge kalmadi: bos ekran (uygulamanin dosyasiz acilisi gibi)."""
        self._aramayi_birak()
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
        self._tuvali_temizle()
        self.satirlar, self.yerler, self._altlar = [], [], []
        self.toplam_yukseklik = 0
        self.aktif_sayfa = 0
        self.tuval.config(scrollregion=(0, 0, 0, 0))
        self.durumu_tazele()

    def belge_listesi(self) -> None:
        """Acik belgeler paneli (B): zathura'nin :open'daki son dosyalari gibi."""
        if self._panel_kapandi("belgeler"):
            return
        if not self.belgeler:
            self.bildir(self.m("belge_listesi_bos"), "uyari")
            return
        self.konumu_kaydet()                    # bakilanin sayfasi guncel gorunsun
        self.panel_konumlari = list(self.belgeler)
        en = max(len(os.path.basename(y)) for y in self.belgeler)
        satirlar = []
        for no, y in enumerate(self.belgeler, 1):
            isaret = ">" if self._ayni_yol(y, self.pdf_yolu) else " "
            sayfa = self.m("satir_sayfa", s=int(self.kalici.dosya(y).get("sayfa", 0)) + 1)
            satirlar.append(f" {isaret} {no:>2}  {os.path.basename(y):<{en}}"
                            f"  {sayfa:>6}   {os.path.dirname(y)}")
        self._paneli_ac("belgeler", satirlar, max(0, self._sira()))

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

    def konumu_kaydet(self, diske: bool = True) -> None:
        """`diske=False`: yalnizca bellekteki kaydi tazeler.

        Fare bolmeler arasinda gezerken her gecis kaydediyor; her seferinde
        durum.json'i yazmak bos yere disk isi olurdu. Dosya zaten kapanista,
        belge degisiminde ve cikista yaziliyor.
        """
        if not self.belge or not self.pdf_yolu:
            return
        kayit = self.kalici.dosya(self.pdf_yolu)
        kayit["konum"] = list(self.konum_imi())
        kayit["sayfa"] = self.aktif_sayfa
        kayit["donme"] = self.donme
        kayit["isaretler"] = {k: list(v) for k, v in self.isaretler.items()}
        if diske:
            self.kalici.yaz()

    # -- duzen -------------------------------------------------------------

    def _sayfa_siniri(self, no: int) -> pymupdf.Rect:
        """Sayfanin donmesiz siniri (pt).

        Sayfa basina bir kez okunur: `belge[no]` sayfayi MuPDF'ten yukler ve
        duzen her yakinlastirmada butun sayfalar icin kurulur (1612 sayfada
        adim basina ~85 ms buraya gidiyordu); her cizimde her arama bulgusu
        da buna bakar.
        """
        r = self._olcu.get(no)
        if r is None:
            r = self._olcu[no] = self.belge[no].rect
        return r

    def sayfa_noktasi(self, no: int) -> tuple[float, float]:
        """Sayfanin nokta (pt) cinsinden, donme uygulanmis olcusu."""
        r = self._sayfa_siniri(no)
        return (r.height, r.width) if self.donme % 180 else (r.width, r.height)

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
        n, zoom = self.belge.page_count, self.zoom
        # Sicak dongu: bolmenin alanlari (zoom, _olcu, sutunlar ...) birer
        # ozellik, her okuma bir cagri. 1612 sayfalik kitapta duzen kurmak
        # bunlari yerele almadan ~%20 uzuyordu; sayfa olcusu de burada, iki
        # ara cagri olmadan okunuyor (bkz. _sayfa_siniri, sayfa_noktasi).
        belge, olcu = self.belge, self._olcu
        sutunlar, devrik = self.sutunlar, bool(self.donme % 180)
        satirlar, yerler = [], []
        y = kenar
        sayfa_olcusu = _sayfa_olcucusu(belge) if len(olcu) < n else None

        for bas in range(0, n, sutunlar):
            pikseller = []
            for no in range(bas, min(bas + sutunlar, n)):
                r = olcu.get(no)
                if r is None:
                    r = olcu[no] = sayfa_olcusu(no)
                w, h = (r.height, r.width) if devrik else (r.width, r.height)
                pikseller.append((no, int(w * zoom), int(h * zoom)))
            top_w = sum(p[1] for p in pikseller) + ara * (len(pikseller) - 1)
            satir_h = max(p[2] for p in pikseller)
            x = max(kenar, (tw - top_w) / 2)

            sayfalar = []
            for no, w, h in pikseller:
                sayfalar.append({"no": no, "x": x, "y": y + (satir_h - h) // 2,
                                 "w": w, "h": h})
                x += w + ara
            satirlar.append({"y": y, "h": satir_h, "sayfalar": sayfalar,
                             "genislik": top_w})
            yerler.extend(sayfalar)
            y += satir_h + ara

        self.satirlar, self.yerler = satirlar, yerler
        self._altlar = [s["y"] + s["h"] for s in satirlar]
        self.toplam_yukseklik = int(y - ara + kenar)
        en_genis = max([s["genislik"] for s in satirlar] or [tw]) + 2 * kenar
        self.toplam_genislik = max(tw, en_genis)
        self.tuval.config(scrollregion=(0, 0, self.toplam_genislik, self.toplam_yukseklik))

    def sayfa_yeri(self, no: int) -> dict | None:
        return self.yerler[no] if 0 <= no < len(self.yerler) else None

    def _satir_indeksi(self, y: float) -> int:
        """Alt kenari y'ye ulasan ilk satir (satirlar yukaridan asagi sirali)."""
        return bisect.bisect_left(self._altlar, y)

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
        i = self._satir_indeksi(ust)
        if i < len(self.satirlar) and self.satirlar[i]["y"] - self.ayar["sayfa-arasi"] <= ust:
            satir = self.satirlar[i]
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
        gece = self._gece_renkleri() if self.ters else None
        anahtar = (no, round(self.zoom, 4), self.donme, self.ters, gece)
        if anahtar in self.onbellek:
            self.onbellek.move_to_end(anahtar)
            return self.onbellek[anahtar]
        try:
            if gece:
                # gri tonla, sonra siyah -> yazi rengi, beyaz -> zemin (R=G=B
                # oldugu icin tint_with'in kanal kanal eslemesi tam bir gecis)
                gri = self.belge[no].get_pixmap(matrix=self.sayfa_matrisi(),
                                                colorspace=pymupdf.csGRAY, alpha=False)
                pix = pymupdf.Pixmap(pymupdf.csRGB, gri)
                pix.tint_with(*gece)
            else:
                pix = self.belge[no].get_pixmap(matrix=self.sayfa_matrisi(), alpha=False)
            if self.ters and not gece:
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
        for satir in self.satirlar[self._satir_indeksi(ust - pay):]:
            if satir["y"] > alt + pay:
                break
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
        self.notlari_ciz(gorunur)
        self.karartmalari_ciz(gorunur)
        if self.baglantilar_acik or self._baglanti_cizili:
            self.baglantilari_ciz(gorunur)
        if self._bekleyen_vurgu:            # yeni islenen sayfanin ustunde kalsin
            self._bekleyeni_ciz()
        if self._capa:
            self._capayi_ciz()
        self.durumu_tazele()

    def _tuvali_temizle(self) -> None:
        self.tuval.delete("all")
        self.tuval_ogeleri.clear()

    def aktif_sayfayi_sapta(self, ust: float) -> None:
        """Ekranin ustten %35'indeki satir; o bosluga duserse ondan sonraki."""
        if self.satirlar:
            i = self._satir_indeksi(ust + self.gorunur_yukseklik() * 0.35)
            self.aktif_sayfa = self.satirlar[min(i, len(self.satirlar) - 1)]["sayfalar"][0]["no"]

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
        self._aramayi_birak()
        self.son_desen = desen
        self._ilk_atlama = False

        n = self.belge.page_count
        bas = self.aktif_sayfa
        if self.arama_yonu < 0:
            self.arama_kuyrugu = [(bas - i) % n for i in range(n)]
        else:
            self.arama_kuyrugu = [(bas + i) % n for i in range(n)]
        self._arama_adimi(self.arama_kimlik)

    def _aramayi_birak(self) -> None:
        self.arama_kimlik += 1          # suren taramayi da durdurur
        self.arama_kuyrugu = []
        self.bulgular, self.bulgu_no = [], -1
        self._aktif_bulgu = None

    # Parti buyudukce tarama hizlanir ama her parti arayuzu o sure kadar bloklar
    # (olcum: ~9 ms/sayfa). 6 sayfa ~55 ms; kaydirma akici kalsin diye bu secildi.
    def _arama_adimi(self, kimlik: int, parti: int = 6) -> None:
        if kimlik != self.arama_kimlik or not self.belge:
            return                       # yeni arama basladi ya da belge kapandi

        for no in self.arama_kuyrugu[:parti]:
            try:
                bulunan = self.belge[no].search_for(self.son_desen)
            except Exception:
                continue
            if not bulunan:
                continue
            # Liste hep belge sirasinda dursun ki n/N beklendigi gibi aksin: sayfanin
            # eslemeleri listedeki yerine eklenir. Her partide butun listeyi
            # yeniden siralamak 100 bin eslemede taramanin %20'sini yiyordu.
            yeni = sorted(((no, r) for r in bulunan), key=lambda b: (b[1].y0, b[1].x0))
            i = bisect.bisect_left(self.bulgular, no, key=lambda b: b[0])
            self.bulgular[i:i] = yeni
            if self._aktif_bulgu is None:           # ilk esleme: sayfadaki okuma sirasiyla ilki
                self._aktif_bulgu = (no, bulunan[0])
                self.bulgu_no = i + yeni.index(self._aktif_bulgu)
            elif i <= self.bulgu_no:                # uzerinde durulan esleme kaydi
                self.bulgu_no += len(yeni)
        del self.arama_kuyrugu[:parti]

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

    def aygit_dikdortgeni(self, sayfa: int, r: pymupdf.Rect, yer: dict,
                          m: pymupdf.Matrix | None = None) -> tuple:
        """PDF nokta uzayindaki dikdortgeni tuval koordinatina cevirir."""
        if m is None:
            m = self.sayfa_matrisi()
        sinir = self._sayfa_siniri(sayfa) * m
        d = r * m
        return (yer["x"] + (d.x0 - sinir.x0), yer["y"] + (d.y0 - sinir.y0),
                yer["x"] + (d.x1 - sinir.x0), yer["y"] + (d.y1 - sinir.y0))

    def bulgulari_ciz(self, gorunur: set[int]) -> None:
        self.tuval.delete("bulgu")
        if not self.bulgular:
            return
        m = self.sayfa_matrisi()                # her bulgu icin yeniden kurulmasin
        for i, (sayfa, r) in enumerate(self.bulgular):
            yer = self.sayfa_yeri(sayfa) if sayfa in gorunur else None
            if not yer:
                continue
            x0, y0, x1, y1 = self.aygit_dikdortgeni(sayfa, r, yer, m)
            renk = self.ayar["arama-aktif" if i == self.bulgu_no else "arama-zemin"]
            self.tuval.create_rectangle(
                x0 - 1, y0 - 1, x1 + 1, y1 + 1, outline=renk, width=1,
                fill=renk, stipple="gray25", tags=("bulgu",),
            )

    # -- baglantilar (<C-l>, tiklama) --------------------------------------
    #
    # "Bu sayfada link var mi?" sorusunun cevabi: <C-l> acikken gorunen
    # sayfalardaki her baglanti (ic atlama da dis URL de) varsayilan vurgu
    # renginde (sari fosfor) isaretlenir.
    #
    # Gostermekten bagimsiz olarak baglantilar **her zaman tiklanir**: imlec
    # uzerine gelince el olur ve durum cubugu hedefi yazar; sol tik ic
    # baglantida (LaTeX'in ref / cite bagi da budur) hedefe ziplar - <C-o>
    # geri getirir -, dis baglantida adresi sistemin varsayilan tarayicisina
    # verir. Kalem acikken ya da Shift basiliyken tik metin secer, baglantiya
    # dokunmaz; sayfayi surukleyen tikta da baglanti acilmaz (bkz. fare_birak).

    def _sayfa_baglanti_kayitlari(self, no: int) -> list[tuple[pymupdf.Rect, dict]]:
        if no not in self._baglantilar:
            try:
                self._baglantilar[no] = [(pymupdf.Rect(b["from"]), b)
                                         for b in self.belge[no].get_links() if "from" in b]
            except Exception:
                self._baglantilar[no] = []
        return self._baglantilar[no]

    def _sayfa_baglantilari(self, no: int) -> list[pymupdf.Rect]:
        return [r for r, _ in self._sayfa_baglanti_kayitlari(no)]

    def noktadaki_baglanti(self, x: float, y: float) -> tuple[dict, dict] | None:
        """Tuval noktasindaki baglanti: (sayfa yeri, baglanti kaydi)."""
        if not self.belge:
            return None
        yer = self._noktadaki_sayfa(x, y)
        if not yer:
            return None
        p = self._sayfa_noktasina(yer, x, y)
        for r, b in self._sayfa_baglanti_kayitlari(yer["no"]):
            if r.contains(p):
                return yer, b
        return None

    def baglanti_ozeti(self, b: dict) -> str:
        """Durum cubugunda gorunen hedef: "-> s. 12" ya da adresin kendisi."""
        tur = b.get("kind")
        if tur == pymupdf.LINK_GOTO:
            return self.m("baglanti_hedef_sayfa", n=int(b.get("page", 0)) + 1)
        if tur == pymupdf.LINK_URI:
            return str(b.get("uri") or "")
        if tur in (pymupdf.LINK_GOTOR, pymupdf.LINK_LAUNCH):
            ad = os.path.basename(str(b.get("file") or ""))
            sayfa = int(b.get("page", -1))
            return f"{ad}  {self.m('baglanti_hedef_sayfa', n=sayfa + 1)}" if sayfa >= 0 else ad
        if tur == pymupdf.LINK_NAMED:
            return str(b.get("name") or b.get("nameddest") or "")
        return ""

    def _gezinme(self, olay) -> None:
        """Tek <Motion> baglantisi: baglanti imleci, not balonu, silme x'i."""
        if self.silme_kipi:
            self._silme_imlecini_ciz(*self._tuval_noktasi(olay))
        self._baglanti_imleci(olay)
        self._not_imleci(olay)

    def _baglanti_imleci(self, olay) -> None:
        """Fare gezerken: baglantinin ustunde el imleci + hedefin ozeti."""
        if self._secim is not None or self._surukleniyor:
            return
        bulgu = self.noktadaki_baglanti(*self._tuval_noktasi(olay))
        kimlik = bulgu[1].get("id") if bulgu else None
        if kimlik == self._imlecteki_baglanti:
            return
        self._imlecteki_baglanti = kimlik
        self.tuval.config(cursor="hand2" if bulgu else "")
        if bulgu:
            self._baglanti_iletisi = self.baglanti_ozeti(bulgu[1]) or self.m("baglanti_bilinmez")
            self.bildir(self._baglanti_iletisi, "vurgu")
        elif self.gecici_ileti and self.gecici_ileti == self._baglanti_iletisi:
            self._baglanti_iletisi = ""
            self.bildir("")

    def baglantiyi_ac(self, yer: dict, b: dict) -> None:
        tur = b.get("kind")
        if tur == pymupdf.LINK_GOTO:
            self.zipla_kaydet()
            self.baglanti_hedefine_git(int(b.get("page", 0)), b.get("to"),
                                       kaynak=(yer["no"], pymupdf.Rect(b["from"])
                                               if "from" in b else None))
        elif tur == pymupdf.LINK_URI:
            self.adresi_ac(str(b.get("uri") or ""))
        elif tur in (pymupdf.LINK_GOTOR, pymupdf.LINK_LAUNCH):
            self.baglanti_belgesini_ac(b)
        elif tur == pymupdf.LINK_NAMED:
            self.adli_hedefe_git(str(b.get("name") or b.get("nameddest") or ""),
                                 kaynak=(yer["no"], pymupdf.Rect(b["from"])
                                         if "from" in b else None))
        else:
            self.bildir(self.m("baglanti_bilinmez"), "uyari")

    def baglanti_hedefine_git(self, sayfa: int, hedef=None, kaynak=None) -> None:
        """Hedef sayfaya gider; `to` varsa o noktayi ekranin ust ucte birine alir.

        `to` yoksa ya da (0,0) ise - yani PDF yalnizca "su sayfa" diyorsa -
        `kaynak` (tiklanan sayfa, tiklanan dikdortgen) verilmisse hedef sayfada
        capa aranir; bulunamazsa sayfanin tepesine gidilir.
        """
        if not self.belge:
            return
        sayfa = max(0, min(self.belge.page_count - 1, sayfa))
        self.sayfaya_git(sayfa, zipla=False)
        yer = self.sayfa_yeri(sayfa)
        if not yer:
            return
        y = None
        if hedef is not None:
            try:
                if abs(float(hedef.x)) > 0.01 or abs(float(hedef.y)) > 0.01:
                    y = float(hedef.y)
            except Exception:
                y = None
        capa = None
        if y is None and kaynak is not None:
            capa = self.baglanti_capasi(sayfa, *kaynak)
            if capa is not None:
                y = capa.y0
        if y is None:                       # PDF de biz de bir sey bilmiyoruz: sayfanin tepesi
            self.ciz()
            return
        # `to` sayfanin (PyMuPDF'in ust-sol) nokta uzayinda; hedefin biraz
        # ustunden basla ki tiklanan baslik ekranin tepesine yapismasin.
        ust = self.aygit_dikdortgeni(sayfa, pymupdf.Rect(0, y, 1, y + 1), yer)[1]
        self.ofset_ata(ust - self.gorunur_yukseklik() * 0.2)
        if capa is not None:
            self.capayi_isaretle(sayfa, capa)
        self.ciz()

    def adli_hedefe_git(self, ad: str, kaynak=None) -> None:
        """Adli hedef (named destination): belgenin kendi tablosundan cozulur."""
        hedef = None
        if ad:
            try:
                hedef = self.belge.resolve_names().get(ad)
            except Exception:
                hedef = None
        if not hedef:
            self.bildir(self.m("baglanti_cozulemedi", ne=ad or "?"), "uyari")
            return
        self.zipla_kaydet()
        nokta = hedef.get("to")
        self.baglanti_hedefine_git(int(hedef.get("page", 0)),
                                   pymupdf.Point(nokta) if nokta else None, kaynak)

    # -- capa: "su sayfa" diyen baglantinin hedefini metinden bul ----------

    def _metin_satirlari(self, no: int) -> list[tuple[str, pymupdf.Rect]]:
        """Sayfanin satirlari (tek boslukla sadelestirilmis metin, dikdortgen).
        Sayfa basina bir kez; tiklama disinda kimse istemez."""
        if no not in self._satir_metinleri:
            satirlar = []
            try:
                sozluk = self.belge[no].get_text("dict")
            except Exception:
                sozluk = {}
            for blok in sozluk.get("blocks", ()):
                for satir in blok.get("lines", ()):
                    metin = " ".join("".join(s.get("text", "")
                                             for s in satir.get("spans", ())).split())
                    if metin:
                        satirlar.append((metin, pymupdf.Rect(satir["bbox"])))
            self._satir_metinleri[no] = satirlar
        return self._satir_metinleri[no]

    def baglanti_capasi(self, hedef: int, kaynak_sayfa: int,
                        kaynak_dik: pymupdf.Rect | None) -> pymupdf.Rect | None:
        """Tiklanan yazidan cikarilan etiketi hedef sayfada arar.

        Once etiketle **baslayan** satir (altyazi, problem numarasi, kaynakca
        girdisi hep oyle yazilir), sonra genisletilmis bicimin satir icinde
        gectigi yer. Ayni sayfaya donen baglantida tiklanan yazinin kendisi
        elenir, yoksa capa oldugun yer olur.
        """
        if kaynak_dik is None:
            return None
        try:
            sayfa = self.belge[kaynak_sayfa]
            adaylar, ciplak = capa_etiketleri(sayfa.get_textbox(kaynak_dik))
            if not adaylar and not ciplak:
                # Dikdortgen yaziyi tam ortmuyor olabilir ("Fig." disarida
                # kalmis): bir kez de biraz genisinden oku.
                genis = pymupdf.Rect(kaynak_dik.x0 - 45, kaynak_dik.y0 - 2,
                                     kaynak_dik.x1 + 15, kaynak_dik.y1 + 2)
                adaylar, ciplak = capa_etiketleri(sayfa.get_textbox(genis))
        except Exception:
            return None
        if not adaylar and not ciplak:
            return None
        ayni = hedef == kaynak_sayfa
        satirlar = self._metin_satirlari(hedef)
        for aday in [a.lower() for a in adaylar] + ([ciplak.lower()] if ciplak else []):
            for metin, r in satirlar:
                if metin.lower().startswith(aday) and not (ayni and r.intersects(kaynak_dik)):
                    return r
        for aday in [a.lower() for a in adaylar]:
            for metin, r in satirlar:
                if aday in metin.lower() and not (ayni and r.intersects(kaynak_dik)):
                    return r
        return None

    def capayi_isaretle(self, sayfa: int, r: pymupdf.Rect) -> None:
        """Gidilen yeri bir an isaretler: ayni sayfaya donen baglantida
        "hicbir sey olmadi" sanilmasin diye."""
        sure = int(self.ayar["capa-suresi"])
        if sure <= 0:                       # isaretleme kapali: eskisi de kalmasin
            self._capayi_birak()
            return
        if self._capa_isi is not None:
            self.after_cancel(self._capa_isi)
        self._capa = (sayfa, r)
        self._capa_isi = self.after(sure, self._capayi_birak)

    def _capayi_birak(self) -> None:
        if self._capa_isi is not None:
            self.after_cancel(self._capa_isi)
            self._capa_isi = None
        self._capa = None
        self.tuval.delete("capa")

    def _capayi_ciz(self) -> None:
        self.tuval.delete("capa")
        if not self._capa:
            return
        sayfa, r = self._capa
        yer = self.sayfa_yeri(sayfa)
        if not yer:
            return
        x0, y0, x1, y1 = self.aygit_dikdortgeni(sayfa, r, yer)
        self.tuval.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 2,
                                    outline=self.ayar["vurgu"], width=2,
                                    fill=self.ayar["vurgu"], stipple="gray12",
                                    tags=("capa",))

    def adresi_ac(self, adres: str) -> None:
        """Dis adresi sisteme verir. Yalnizca bu semalar: bir PDF'in icinden
        gelen `javascript:` / `file:` / `cmd:` gibi bir adresi acmak tehlikeli."""
        adres = adres.strip()
        if not adres:
            return
        if not adres.lower().startswith(("http://", "https://", "mailto:", "ftp://", "ftps://")):
            self.bildir(self.m("baglanti_guvensiz", ne=adres[:80]), "uyari")
            return
        try:
            os.startfile(adres)                     # ShellExecute: varsayilan tarayici
        except Exception as e:
            self.bildir(self.m("baglanti_acilamadi", e=e), "hata")
            return
        self.bildir(self.m("baglanti_acildi", ne=adres[:80]), "vurgu")

    def baglanti_belgesini_ac(self, b: dict) -> None:
        """Baska bir dosyaya giden baglanti: PDF ise rubric'te acilir, digeri
        (LAUNCH) acilmaz - bir belgenin istedigi programi calistirmasi olmaz."""
        dosya = str(b.get("file") or "").strip()
        if not dosya:
            return
        # Bazi kitaplar web adresini LAUNCH olarak gomuyor (temiz2.pdf'te 14
        # tane: "www.pearsonglobaleditions.com"). Dosya degil adres: tarayiciya.
        if re.match(r"^(?:https?://|www\.[\w\-]+\.\w)", dosya, re.I):
            self.adresi_ac(dosya if "://" in dosya else "http://" + dosya)
            return
        if not os.path.isabs(dosya) and self.pdf_yolu:
            dosya = os.path.join(os.path.dirname(self.pdf_yolu), dosya)
        if os.path.splitext(dosya)[1].lower() != ".pdf":
            self.bildir(self.m("baglanti_guvensiz", ne=os.path.basename(dosya)), "uyari")
            return
        if not os.path.exists(dosya):
            self.bildir(self.m("bulunamadi", ne=dosya), "hata")
            return
        self.belgeyi_ac(dosya)
        sayfa = int(b.get("page", -1))
        if sayfa >= 0:
            self.baglanti_hedefine_git(sayfa, b.get("to"))

    def baglantilari_ciz(self, gorunur: set[int]) -> None:
        self.tuval.delete("baglanti")
        self._baglanti_cizili = False
        if not self.baglantilar_acik or not self.belge:
            return
        renk = self.ayar["vurgu-rengi"]
        m = self.sayfa_matrisi()
        for no in gorunur:
            yer = self.sayfa_yeri(no)
            if not yer:
                continue
            for r in self._sayfa_baglantilari(no):
                x0, y0, x1, y1 = self.aygit_dikdortgeni(no, r, yer, m)
                self.tuval.create_rectangle(x0 - 1, y0 - 1, x1 + 1, y1 + 1, outline=renk,
                                            width=2, fill=renk, stipple="gray25",
                                            tags=("baglanti",))
                self._baglanti_cizili = True

    def baglantilari_goster(self) -> None:
        if not self.belge:
            return
        self.baglantilar_acik = not self.baglantilar_acik
        self.ciz()
        if not self.baglantilar_acik:
            self.bildir(self.m("baglanti_kapali"), "vurgu")
            return
        n = len(self._sayfa_baglantilari(self.aktif_sayfa))
        if n:
            self.bildir(self.m("baglanti_var", n=n), "vurgu")
        else:
            self.bildir(self.m("baglanti_yok"), "uyari")

    def vurguyu_kapat(self) -> None:
        self._aramayi_birak()
        self.tuval.delete("bulgu")
        if self.kalem or self.silme_kipi or self.karartma_acik:   # Esc kalemleri ve silme kipini birakir
            self.kalem = False
            self._silme_kipini_kapat()
            self._karartma_kalemini_birak()
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

    def vurgu_hex(self, v: dict) -> str:
        """Vurgunun rengi; renksiz (eski) ya da "sari" olan temanin vurgu-rengi."""
        return VURGU_RENKLERI.get(v.get("renk", "sari")) or self.ayar["vurgu-rengi"]

    def _not_yaz(self, belge: pymupdf.Document, v: dict):
        """Vurguyu `belge`ye highlight notu olarak ekler (yazdirma kopyasi da kullanir)."""
        sayfa = belge[int(v["sayfa"])]
        not_ = sayfa.add_highlight_annot(quads=[pymupdf.Rect(d).quad for d in v["dikler"]])
        not_.set_colors(stroke=rgb(self.vurgu_hex(v)))
        not_.set_info(title="rubric", subject=v["kimlik"], content=v.get("metin", ""))
        not_.update()
        return not_

    def _notu_ekle(self, v: dict) -> bool:
        """Vurguyu bellekteki belgeye highlight notu olarak isler."""
        if not self.belge.is_pdf:
            return False
        try:
            self._vurgu_xref[v["kimlik"]] = self._not_yaz(self.belge, v).xref
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
            self.geri_yigini.append(("vurgu-sil", v, None))   # U da geri getirsin
        self._vurgulari_kaydet()
        self._sayfayi_tazele(int(v["sayfa"]))

    # -- kenar notlari (i) -------------------------------------------------
    #
    # Not serbest bir noktaya iliskir, vurguya degil: sayfanin herhangi bir
    # yerine `i` ile dusulur. Kayit durum.json'da, dosya kaydinin `notlar`
    # listesinde ve **sayfa nokta uzayinda** ({sayfa, x, y, metin}) - yani
    # zoom, donme ve pencere boyu degisince not yerinde kalir. PDF dosyasina
    # yazilmaz; vurgularin aksine bellekteki belgeye de not eklenmez, isaret
    # dogrudan tuvale cizilir (sayfa resmi onbellege girdigi icin annotation
    # olsaydi her degisiklikte sayfayi yeniden islemek gerekirdi).
    #
    # Isaret: [n] - sayfa uzerinde sabit piksel boyunda durur, zoom'la
    # buyumez. Uzerine gelince notun kendisi koyu bir balonda acilir, fare
    # cekilince kapanir (bkz. _not_balonu_goster).
    #
    # Isaretin altinda ince bir plaka var: sayfa beyaz olmayabiliyor (kapak
    # gorseli, koyu sekil, tablo zemini) ve ciplak [n] oralarda kayboluyordu.
    # Plaka balonla ayni renkleri kullanir, yani isaret balonun kucuk hali
    # gibi durur.

    NOT_ISARETI = "[n]"
    NOT_PAYI = (4, 1)                   # plakanin yatay / dikey payi (px)

    def _notlari_yukle(self, kayit: dict) -> None:
        self.notlar = [n for n in kayit.get("notlar", [])
                       if isinstance(n, dict) and str(n.get("metin", "")).strip()
                       and 0 <= int(n.get("sayfa", -1)) < self.belge.page_count]

    def _notlari_kaydet(self) -> None:
        """Hemen diske: uygulama cokerse de not kaybolmasin (vurgular gibi)."""
        kayit = self.kalici.dosya(self.pdf_yolu)
        if self.notlar:
            kayit["notlar"] = self.notlar
        else:
            kayit.pop("notlar", None)
        self.kalici.yaz()

    def _not_yazitipi(self) -> tuple:
        return (self.ayar["yazitipi"], max(8, int(self.ayar["yazitipi-boy"])), "bold")

    def _not_kutusu(self, n: dict, m: pymupdf.Matrix | None = None) -> tuple | None:
        """Isaretin tuvaldeki dikdortgeni; sayfa gorunur degilse None."""
        sayfa = int(n["sayfa"])
        yer = self.sayfa_yeri(sayfa)
        if not yer:
            return None
        nokta = pymupdf.Rect(n["x"], n["y"], n["x"], n["y"])
        x0, y0, _x1, _y1 = self.aygit_dikdortgeni(sayfa, nokta, yer, m)
        yatay, dikey = self.NOT_PAYI
        en, boy = self._not_olcusu()
        return (x0 - yatay, y0 - boy / 2 - dikey, x0 + en + yatay, y0 + boy / 2 + dikey)

    def _not_olcusu(self) -> tuple[int, int]:
        """[n]'in piksel olcusu. Olcum onbellekte: cizim her karede butun
        gorunur notlar icin cagiriliyor, her seferinde Font kurmak israf."""
        yt = self._not_yazitipi()
        if getattr(self, "_not_olcu_anahtar", None) != yt:
            yf = tkfont.Font(font=yt)
            self._not_olcu_anahtar = yt
            self._not_olcu = (yf.measure(self.NOT_ISARETI), yf.metrics("linespace"))
        return self._not_olcu

    def notlari_ciz(self, gorunur: set[int]) -> None:
        self.tuval.delete("not")
        if not self.notlar:
            return
        m = self.sayfa_matrisi()            # her not icin yeniden kurulmasin
        yatay, _dikey = self.NOT_PAYI
        for n in self.notlar:
            if int(n["sayfa"]) not in gorunur:
                continue
            kutu = self._not_kutusu(n, m)
            if kutu is None:
                continue
            x0, y0, x1, y1 = kutu
            self.tuval.create_rectangle(x0, y0, x1, y1, fill=self.ayar["palet-zemin"],
                                        outline=self.ayar["palet-cerceve"], tags=("not",))
            self.tuval.create_text(x0 + yatay, (y0 + y1) / 2, text=self.NOT_ISARETI,
                                   anchor="w", fill=self.ayar["vurgu"],
                                   font=self._not_yazitipi(), tags=("not",))

    def noktadaki_not(self, x: float, y: float) -> dict | None:
        m = self.sayfa_matrisi()
        for n in self.notlar:
            kutu = self._not_kutusu(n, m)
            if kutu and kutu[0] <= x <= kutu[2] and kutu[1] <= y <= kutu[3]:
                return n
        return None

    # Balon tuvale cizilir, ayri bir Toplevel degil: overrideredirect bir
    # pencere Windows'ta odagi kimi zaman kapiyor ve kaydirmada geride
    # kaliyor. Tuvale cizilince sayfayla birlikte hareket eder ve temanin
    # renklerini zaten kullanir.

    def _not_balonu_goster(self, n: dict) -> None:
        self.tuval.delete("not-balon")
        kutu = self._not_kutusu(n)
        if kutu is None:
            return
        pay, kenar = 7, 10
        en_cok = max(180, int(self.tuval.winfo_width() * 0.42))
        metin = self.tuval.create_text(0, 0, text=n["metin"], anchor="nw", width=en_cok,
                                       fill=self.ayar["cubuk-on"], font=(self.ayar["yazitipi"],
                                       max(8, int(self.ayar["yazitipi-boy"]))),
                                       tags=("not-balon",))
        mx0, my0, mx1, my1 = self.tuval.bbox(metin)
        en, boy = (mx1 - mx0) + pay * 2, (my1 - my0) + pay * 2

        # Isaretin sagina; ekranin sagina sigmiyorsa soluna gecer.
        x = kutu[2] + kenar
        if x + en > self.tuval.canvasx(0) + self.tuval.winfo_width():
            x = max(self.tuval.canvasx(0), kutu[0] - kenar - en)
        y = kutu[1]
        alt_sinir = self.tuval.canvasy(0) + self.tuval.winfo_height()
        if y + boy > alt_sinir:
            y = max(self.tuval.canvasy(0), alt_sinir - boy)

        zemin = self.tuval.create_rectangle(x, y, x + en, y + boy,
                                            fill=self.ayar["palet-zemin"],
                                            outline=self.ayar["palet-cerceve"],
                                            tags=("not-balon",))
        self.tuval.coords(metin, x + pay, y + pay)
        self.tuval.tag_raise(zemin)
        self.tuval.tag_raise(metin)
        self._imlecteki_not = n

    def _not_balonu_gizle(self) -> None:
        if self._imlecteki_not is None:
            return
        self.tuval.delete("not-balon")
        self._imlecteki_not = None

    def _not_imleci(self, olay) -> None:
        """Fare gezerken: isaretin ustundeyse balonu ac, cekilince kapat."""
        if self._secim is not None or self._surukleniyor:
            return
        n = self.noktadaki_not(*self._tuval_noktasi(olay))
        if n is self._imlecteki_not:
            return
        if n is None:
            self._not_balonu_gizle()
        else:
            self._not_balonu_goster(n)

    # -- not yazma / duzenleme --------------------------------------------

    def not_ekle(self) -> None:
        """`i`: imlecin altinda not varsa onu duzenler, yoksa oraya yenisini acar."""
        if not self.belge:
            return
        x, y = self._fare_tuval_noktasi()
        varolan = self.noktadaki_not(x, y)
        if varolan is not None:
            self._duzenlenen_not = varolan
            self.not_modu(varolan["metin"])
            return
        s = self._noktadaki_sayfa(x, y)
        if s is None:
            self.bildir(self.m("not_sayfa_disi"), "uyari")
            return
        nokta = self._sayfa_noktasina(s, x, y)
        self._duzenlenen_not = {"sayfa": s["no"], "x": nokta.x, "y": nokta.y, "metin": ""}
        self.not_modu("")

    def _fare_tuval_noktasi(self) -> tuple[float, float]:
        """Farenin o anki yeri, tuval koordinatinda. Tus basildigi anda
        okunur: `i` klavyeden geliyor, yaninda bir fare olayi gelmiyor."""
        px, py = self.winfo_pointerxy()
        return (self.tuval.canvasx(px - self.tuval.winfo_rootx()),
                self.tuval.canvasy(py - self.tuval.winfo_rooty()))

    def not_onayla(self, metin: str) -> None:
        """Komut satirindan gelen metni isler. Bos metin notu siler."""
        n, self._duzenlenen_not = self._duzenlenen_not, None
        if n is None:
            return
        metin = metin.strip()
        if not metin:
            if n in self.notlar:
                self._not_sil(n)
                self.bildir(self.m("not_silindi"), "vurgu")
            else:
                self._not_balonu_gizle()    # hic yazilmadan bosa onaylandi
            return
        if n not in self.notlar:
            n["metin"] = metin
            n["zaman"] = time.time()
            self._not_ekle(n)
            self.bildir(self.m("not_eklendi"), "vurgu")
            return
        eski, n["metin"] = n["metin"], metin
        if eski != metin:
            self.geri_yigini.append(("not-duzenle", n, eski))
        self._notlari_kaydet()
        self._not_balonu_gizle()
        self.ciz()
        self.bildir(self.m("not_guncellendi"), "vurgu")

    # -- silme / geri getirme ----------------------------------------------
    #
    # `geri_yigini` tek bir zaman cizgisi: not ekleme/silme/duzenlemesi VE
    # silinen vurgular. `U` (geri-getir) tepesindekini geri alir - silme
    # kipinde ikisini de silebildigin icin geri getirmenin de tek tus olmasi
    # gerekiyor.
    #
    # `u` (vurgu-geri-al) eskisi gibi duruyor ve yalniz vurgulara bakiyor.
    # Bir vurgu silmesi iki yigina birden yazilir; ikisinden biri onu geri
    # getirdiginde oteki yiginda kalan kayit **olu** olur. Bu yuzden geri
    # getirme her adimda "zaten yerinde mi" diye bakip olu kaydi atlar -
    # yoksa ayni vurgu iki kez eklenirdi.

    def _not_ekle(self, n: dict, gecmise: bool = True) -> None:
        self.notlar.append(n)
        if gecmise:
            self.geri_yigini.append(("not-ekle", n, None))
        self._notlari_kaydet()
        self._not_balonu_gizle()
        self.ciz()

    def _not_sil(self, n: dict, gecmise: bool = True) -> None:
        if n not in self.notlar:
            return
        self.notlar.remove(n)
        if gecmise:
            self.geri_yigini.append(("not-sil", n, None))
        self._notlari_kaydet()
        self._not_balonu_gizle()
        self.ciz()

    def geri_getir(self) -> None:
        """`U`: son silineni geri getirir; not duzenlemesini de geri alir.

        Yigindaki kayit baska bir yoldan (`u`) zaten geri alinmissa olu
        sayilir ve atlanir - bir alttakine bakilir."""
        while self.geri_yigini:
            islem, nesne, eski = self.geri_yigini.pop()
            if islem == "not-sil":
                if nesne in self.notlar:
                    continue                    # olu kayit
                self._not_ekle(nesne, gecmise=False)
                self.bildir(self.m("not_geri_geldi"), "vurgu")
            elif islem == "not-ekle":
                if nesne not in self.notlar:
                    continue
                self._not_sil(nesne, gecmise=False)
                self.bildir(self.m("not_geri_alindi"), "vurgu")
            elif islem == "karartma-ekle":
                kalan = [k for k in nesne if k in self.karartmalar]
                if not kalan:
                    continue
                for k in kalan:
                    self.karartmalar.remove(k)
                self.karartmalari_ciz()
                self.bildir(self.m("karartma_geri"), "vurgu")
            elif islem == "not-duzenle":
                if nesne not in self.notlar:
                    continue
                nesne["metin"] = eski
                self._notlari_kaydet()
                self._not_balonu_gizle()
                self.ciz()
                self.bildir(self.m("not_geri_alindi"), "vurgu")
            else:                               # vurgu-sil
                if nesne in self.vurgular:
                    continue
                self._vurgu_ekle(nesne, gecmise=False)
                self.bildir(self.m("vurgu_geri_geldi"), "vurgu")
            return
        self.bildir(self.m("geri_getirilecek_yok"), "uyari")

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
        if self.kalem:
            self._silme_kipini_kapat()      # ikisi ayni anda anlamsiz
            self._karartma_kalemini_birak()
        self.tuval.config(cursor="xterm" if self.kalem else "")
        self.bildir(self.m("kalem_acik" if self.kalem else "kalem_kapali"), "vurgu")

    # -- silme kipi (<Delete>) ---------------------------------------------
    #
    # Acikken tiklanan sey silinir: once not, altinda vurgu. Kip tek tikta
    # kapanmaz - arka arkaya temizlemek icin acik kalir, <Esc> ya da yine
    # <Delete> kapatir. Silinen her sey `geri_yigini`na yazilir, `U` ya da
    # <C-z> geri getirir (vurgu ayrica `u` ile de).

    def _silme_kipini_kapat(self) -> None:
        """Kipi ve okun ucundaki x'i birlikte kaldirir. Tek yerde durmali:
        kip uc ayri yoldan kapaniyor (<Delete>, <Esc>, kalemi acmak) ve
        birinde x'i silmeyi unutmak ekranda asili bir isaret birakiyor."""
        self.silme_kipi = False
        self.tuval.delete("silme-imleci")

    def silme_kipi_degistir(self) -> None:
        if not self.belge:
            return
        if self.silme_kipi:
            self._silme_kipini_kapat()
            self.bildir(self.m("silme_kapali"), "vurgu")
            return
        self.silme_kipi = True
        self.kalem = False                  # ikisi ayni anda anlamsiz
        self._karartma_kalemini_birak()
        # Sistem imleci ok olarak kalir: "bu tik siler" bilgisini okun ucuna
        # cizdigimiz x veriyor (bkz. _silme_imlecini_ciz).
        self.tuval.config(cursor="")
        self.bildir(self.m("silme_acik"), "uyari")

    def _silme_imlecini_ciz(self, x: float, y: float) -> None:
        """Imlecin ucuna kucuk bir x: linux'taki xkill gibi, "bu tik siler"
        oldugu bakinca anlasilsin. Sistem imleci ok olarak kalir; x onun
        sag altina, okun isaret ettigi noktanin yaninda durur."""
        self.tuval.delete("silme-imleci")
        if not self.silme_kipi:
            return
        d, kol = 11, 4                      # okun ucundan uzaklik, x'in kolu
        mx, my = x + d, y + d
        for ax, ay, bx, by in ((-kol, -kol, kol, kol), (-kol, kol, kol, -kol)):
            self.tuval.create_line(mx + ax, my + ay, mx + bx, my + by,
                                   fill=self.ayar["hata"], width=2,
                                   capstyle="butt", tags=("silme-imleci",))
        self.tuval.tag_raise("silme-imleci")

    def _silme_tiki(self, x: float, y: float) -> None:
        """Silme kipinde sol tik: noktadaki notu, yoksa vurguyu siler."""
        n = self.noktadaki_not(x, y)
        if n is not None:
            self._not_sil(n)
            self.bildir(self.m("not_silindi"), "vurgu")
            return
        v = self.noktadaki_vurgu(x, y)
        if v is not None:
            self._vurgu_sil(v)
            self.bildir(self.m("vurgu_silindi"), "vurgu")
            return
        self.bildir(self.m("silinecek_yok"), "uyari")

    # -- vurgu: fare ve secim ---------------------------------------------

    def _tuval_noktasi(self, olay) -> tuple[float, float]:
        return self.tuval.canvasx(olay.x), self.tuval.canvasy(olay.y)

    def _noktadaki_sayfa(self, x: float, y: float) -> dict | None:
        for satir in self.satirlar[self._satir_indeksi(y):]:
            if satir["y"] > y:
                break
            for s in satir["sayfalar"]:
                if s["x"] <= x <= s["x"] + s["w"] and s["y"] <= y <= s["y"] + s["h"]:
                    return s
        return None

    def _sayfa_noktasina(self, yer: dict, x: float, y: float) -> pymupdf.Point:
        """Tuval koordinati -> sayfanin nokta uzayi (aygit_dikdortgeni'nin tersi)."""
        m = self.sayfa_matrisi()
        sinir = self._sayfa_siniri(yer["no"]) * m
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
        m = self.sayfa_matrisi()
        for d in self._secim_dikleri()[0]:
            x0, y0, x1, y1 = self.aygit_dikdortgeni(s["sayfa"], pymupdf.Rect(d), yer, m)
            self.tuval.create_rectangle(x0, y0, x1, y1, outline=renk, fill=renk,
                                        stipple="gray50", tags=("secim",))

    def secim_bitir(self, olay=None) -> None:
        """Birakilan secim hemen boyanmaz, renk bekler (bkz. tus_geldi):
        Enter varsayilan renk, renk tusu (b: mavi ...) o renk, Esc birakir."""
        s, self._secim = self._secim, None
        self.tuval.delete("secim")
        if not s or not s["oynadi"]:
            self._secimi_birak()                  # tik: vurgu yok, bekleyen secim de duser
            return
        self._secim = s
        dikler, metin = self._secim_dikleri()
        self._secim = None
        if not dikler:
            self.bildir(self.m("secilecek_metin_yok"), "uyari")
            return
        self._bekleyen_vurgu = {"sayfa": s["sayfa"], "dikler": dikler, "metin": metin}
        self._bekleyeni_ciz()
        tuslar = "  ".join(f"{t}:{self.renk_adi(r)}" for t, r in self.renk_tuslari().items())
        kisa = metin if len(metin) <= 30 else metin[:27] + "..."
        self.bildir(self.m("secim_bekliyor", metin=kisa,
                           varsayilan=self.renk_adi(self.vurgu_varsayilani()),
                           tuslar=tuslar), "vurgu")

    def kopyala(self) -> None:
        """<C-c>: renk bekleyen secimin (Shift+surukle) metni panoya. Secim
        yerinde kalir; ardindan yine boyanabilir ya da Esc ile birakilir."""
        b = self._bekleyen_vurgu
        if not b or not b.get("metin"):
            self.bildir(self.m("kopyalanacak_yok"), "uyari")
            return
        self.clipboard_clear()
        self.clipboard_append(b["metin"])
        kisa = b["metin"] if len(b["metin"]) <= 48 else b["metin"][:45] + "..."
        self.bildir(self.m("kopyalandi", metin=kisa), "vurgu")

    def _bekleyeni_ciz(self) -> None:
        """Renk bekleyen secim: vurgu-rengi taramali, cercevesi arayuz vurgusunda
        (henuz boyanmamis oldugu belli olsun)."""
        self.tuval.delete("bekleyen")
        b = self._bekleyen_vurgu
        yer = self.sayfa_yeri(b["sayfa"]) if b else None
        if not yer:
            return
        m = self.sayfa_matrisi()
        for d in b["dikler"]:
            x0, y0, x1, y1 = self.aygit_dikdortgeni(b["sayfa"], pymupdf.Rect(d), yer, m)
            self.tuval.create_rectangle(x0 - 1, y0 - 1, x1 + 1, y1 + 1, outline=self.ayar["vurgu"],
                                        fill=self.ayar["vurgu-rengi"], stipple="gray50",
                                        tags=("bekleyen",))

    def _secimi_birak(self) -> None:
        self._bekleyen_vurgu = None
        self.tuval.delete("bekleyen")

    def bekleyeni_vurgula(self, renk: str) -> None:
        """Renk bekleyen secimi `renk`le vurguya cevirir."""
        b = self._bekleyen_vurgu
        self._secimi_birak()
        if not b:
            return
        v = {"kimlik": f"{time.time_ns():x}", "sayfa": b["sayfa"], "dikler": b["dikler"],
             "metin": b["metin"], "zaman": time.strftime("%Y-%m-%d %H:%M")}
        if renk != "sari":                        # varsayilan yazilmaz: temayla degissin
            v["renk"] = renk
        self._vurgu_ekle(v)
        kisa = b["metin"] if len(b["metin"]) <= 48 else b["metin"][:45] + "..."
        self.bildir(self.m("vurgulandi", metin=kisa), "vurgu")

    def renk_adi(self, renk: str) -> str:
        return RENK_ADLARI.get(self.ayar["dil"], RENK_ADLARI["en"]).get(renk, renk)

    def vurgu_varsayilani(self) -> str:
        """Enter'in koydugu renk (`vurgu-varsayilan`); bozuksa "sari"ya duser."""
        renk = str(self.ayar.get("vurgu-varsayilan", "sari")).strip().lower()
        return renk if renk in VURGU_RENKLERI else "sari"

    def renk_tuslari(self) -> dict[str, str]:
        """`vurgu-tuslari` ayari: tus -> renk ("b:mavi g:yesil"; tus `<C-b>` de olabilir)."""
        sonuc: dict[str, str] = {}
        for parca in str(self.ayar["vurgu-tuslari"]).split():
            tus, _, renk = parca.rpartition(":")
            if tus and renk in VURGU_RENKLERI:
                sonuc[tus] = renk
        return sonuc

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
        # Palet acikken belgeye tiklamak paleti kapatir - disari tiklamak
        # "vazgectim" demenin dogal yolu. Tik yalnizca kapatir; altindaki
        # sayfada kaydirma/secim baslatmaz, baglanti da acmaz.
        if self.mod == "palet":
            self.paleti_kapat()
            return
        self.tuval.focus_set()
        # Silme kipi: tik yalnizca siler - kaydirma / secim baslatmaz,
        # altindaki baglantiyi da acmaz.
        if self.silme_kipi:
            self._silme_tiki(*self._tuval_noktasi(olay))
            return
        if self.karartma_acik:
            self._karartma_basla(*self._tuval_noktasi(olay))
            return
        self._baglanti_adayi = None
        if self.belge and self.belge.is_pdf and (self.kalem or olay.state & 0x1):
            self.secim_basla(olay)
        else:
            self._secim = None
            # Baglanti basarken degil birakirken acilir: basili tutup sayfayi
            # kaydirmak da ayni tusla oluyor, kaydirilmissa tik sayilmaz.
            self._baglanti_adayi = self.noktadaki_baglanti(*self._tuval_noktasi(olay))
            self._basis_noktasi = (olay.x, olay.y)
            self._surukleniyor = True
            self.surukle_basla(olay)

    def fare_surukle(self, olay) -> None:
        if self._karartma_cizimi is not None:
            self._karartma_surukle(*self._tuval_noktasi(olay))
            return
        if self._secim is not None:
            self.secim_surukle(olay)
            return
        if self._baglanti_adayi is not None and self._basis_noktasi and \
                abs(olay.x - self._basis_noktasi[0]) + abs(olay.y - self._basis_noktasi[1]) > 4:
            self._baglanti_adayi = None       # kaydirmaya donustu
        self.surukle(olay)

    def fare_birak(self, olay) -> None:
        if self._karartma_cizimi is not None:
            self._karartma_bitir()
            return
        if self._secim is not None:
            self.secim_bitir(olay)
            return
        self._surukleniyor = False
        aday, self._baglanti_adayi = self._baglanti_adayi, None
        if aday is None:
            return
        simdiki = self.noktadaki_baglanti(*self._tuval_noktasi(olay))
        if simdiki and simdiki[1].get("id") == aday[1].get("id"):
            self.baglantiyi_ac(*simdiki)

    def _baglantidan_cik(self, _olay=None) -> None:
        """Imlec tuvalden cikinca el imleci ve hedef ozeti uzerinde kalmasin."""
        if self._imlecteki_baglanti is None:
            return
        self._imlecteki_baglanti = None
        self.tuval.config(cursor="")
        if self.gecici_ileti and self.gecici_ileti == self._baglanti_iletisi:
            self._baglanti_iletisi = ""
            self.bildir("")

    # -- vurgu: liste ve disa aktarma -------------------------------------

    def vurgu_listesi(self) -> None:
        if not self.belge or self._panel_kapandi("vurgular"):
            return
        if not self.vurgular:
            self.bildir(self.m("belgede_vurgu_yok"), "uyari")
            return
        sirali = sorted(self.vurgular, key=lambda v: (int(v["sayfa"]), v["dikler"][0][1]))
        self.panel_konumlari = sirali
        secim = 0
        for i, v in enumerate(sirali):
            if int(v["sayfa"]) <= self.aktif_sayfa:
                secim = i
        satirlar = [f"  [{int(v['sayfa']) + 1:>4}]  {' '.join(v.get('metin', '').split())}"
                    for v in sirali]
        self._paneli_ac("vurgular", satirlar, secim)
        for i, v in enumerate(sirali):              # renkli vurgu kendi renginde okunsun
            if v.get("renk") in VURGU_RENKLERI and v["renk"] != "sari" \
                    and kontrast(self.vurgu_hex(v), self.ayar["panel-zemin"]) >= 3:
                self.liste.itemconfig(i, foreground=self.vurgu_hex(v))

    def _vurguya_git(self, v: dict) -> None:
        yer = self.sayfa_yeri(int(v["sayfa"]))
        if not yer:
            return
        self.zipla_kaydet()
        d = self.aygit_dikdortgeni(int(v["sayfa"]), pymupdf.Rect(v["dikler"][0]), yer)
        self.ofset_ata(d[1] - self.gorunur_yukseklik() * 0.35)
        self.ciz()

    # -- PDF araclari -------------------------------------------------------
    #
    # vurgulari-aktar, birlestir, ustveri-temizle, karartma ve sayfa duzeni
    # ayni kurala uyar: bakilan belgenin **diskteki** halinden bir kopya
    # acilir, is onun ustunde yapilir ve `<ad>-<ek>.pdf` diye YENI bir dosyaya
    # yazilir. Asil dosyaya hic dokunulmaz, var olan bir dosyanin ustune de
    # yazilmaz (bkz. _yeni_dosya_adi).

    def _pdf_hazir(self) -> bool:
        if not self.belge or not self.pdf_yolu:
            return False
        if not self.belge.is_pdf:
            self.bildir(self.m("pdf_gerek"), "uyari")
            return False
        return True

    def _yeni_dosya_adi(self, ek: str) -> str:
        """`<ad>-<ek>.pdf`, belgenin yaninda; varsa -2, -3 ..."""
        kok, _ = os.path.splitext(self.pdf_yolu)
        hedef, n = f"{kok}-{ek}.pdf", 2
        while os.path.exists(hedef):
            hedef, n = f"{kok}-{ek}-{n}.pdf", n + 1
        return hedef

    def _taze_kopya(self) -> pymupdf.Document:
        """Belgenin diskteki hali. Bellekteki belgede vurgular highlight notu
        olarak islenmis durur; ondan yazsak birlestirilen, karartilan ya da
        temizlenen kopyaya vurgular da sessizce girerdi."""
        return pymupdf.open(self.pdf_yolu)

    def vurgulari_aktar(self) -> None:
        """Vurgular highlight, kenar notlari yapiskan not (Text annotation)
        olarak kopyaya gomulur: Acrobat'ta, tarayicida, telefonda gorunurler."""
        if not self._pdf_hazir():
            return
        if not self.vurgular and not self.notlar:
            self.bildir(self.m("aktarilacak_yok"), "uyari")
            return
        hedef = self._yeni_dosya_adi(self.m("vurgulu_ek"))   # <ad>-highlighted.pdf / -vurgulu / -markiert
        try:
            with self._taze_kopya() as kopya:
                for v in self.vurgular:
                    self._not_yaz(kopya, v)
                for n in self.notlar:
                    self._kenar_notu_yaz(kopya, n)
                kopya.save(hedef, garbage=1, deflate=True)
        except Exception as e:
            self.bildir(self.m("aktarilamadi", e=e), "hata")
            return
        ne = [self.m(anahtar, n=len(liste)) for anahtar, liste in
              (("vurgu_n", self.vurgular), ("not_n", self.notlar)) if liste]
        self.bildir(self.m("aktarildi", vurgular=", ".join(ne),
                           ad=os.path.basename(hedef)), "vurgu")

    def _kenar_notu_yaz(self, belge: pymupdf.Document, n: dict):
        """Kenar notunu `belge`ye yapiskan not olarak ekler. Nokta vurgularla
        ayni uzayda (sayfanin kelime koordinatlari), donuk sayfada da yerinde."""
        sayfa = belge[int(n["sayfa"])]
        not_ = sayfa.add_text_annot(pymupdf.Point(n["x"], n["y"]), n["metin"], icon="Note")
        not_.set_colors(stroke=rgb(self.ayar["vurgu-rengi"]))
        not_.set_info(title="rubric", content=n["metin"])
        not_.update()
        return not_

    # -- birlestir -----------------------------------------------------------

    def birlestir(self) -> None:
        """Secilen PDF'leri bakilan belgenin arkasina ekler, sonucu acar."""
        if not self._pdf_hazir():
            return
        yollar = filedialog.askopenfilenames(
            title=self.m("birlestir_baslik"),
            filetypes=[("PDF", "*.pdf"), (self.m("ac_tumu"), "*.*")])
        if yollar:
            self.birlestir_yaz(list(yollar))

    def birlestir_yaz(self, yollar: list[str]) -> str | None:
        """Icindekilerde her dosya kendi adiyla ust baslik olur, kendi
        basliklari onun altina kayar - Acrobat'in "dosyalari birlestir"i gibi.
        PDF olmayan (epub, xps ...) once PDF'e cevrilir."""
        hedef = self._yeni_dosya_adi(self.m("birlesik_ek"))
        try:
            with self._taze_kopya() as sonuc:
                icindekiler = [[1, os.path.basename(self.pdf_yolu), 1]]
                icindekiler += [[d + 1, b, s] for d, b, s in sonuc.get_toc()]
                for yol in yollar:
                    with pymupdf.open(yol) as ek:
                        kaynak = ek if ek.is_pdf else pymupdf.open("pdf", ek.convert_to_pdf())
                        bas = sonuc.page_count
                        sonuc.insert_pdf(kaynak)
                        icindekiler.append([1, os.path.basename(yol), bas + 1])
                        icindekiler += [[d + 1, b, s + bas if s > 0 else s]
                                        for d, b, s in kaynak.get_toc()]
                try:
                    sonuc.set_toc(icindekiler)
                except Exception:
                    pass                # bozuk bir icindekiler birlestirmeyi durdurmasin
                sayfalar = sonuc.page_count
                sonuc.save(hedef, garbage=3, deflate=True)
        except Exception as e:
            self.bildir(self.m("yazilamadi", e=e), "hata")
            return None
        self.belgeyi_ac(hedef)
        self.bildir(self.m("birlestirildi", n=len(yollar) + 1,
                           sayfalar=self.m("sayfa_n", n=sayfalar),
                           ad=os.path.basename(hedef)), "vurgu")
        return hedef

    # -- ustveri temizle -----------------------------------------------------

    USTVERI_ALANLARI = ("title", "author", "subject", "keywords", "creator",
                        "producer", "creationDate", "modDate", "trapped")

    def ustveri_temizle(self) -> None:
        """Belge bilgisi (yazar, program, tarihler), XMP ve yorumlarin yazar
        adi silinir. garbage=4 sart: eski bilgi nesnesi dosyada sahipsiz
        kalmasin, gercekten gitsin (testte ham baytlara bakiliyor)."""
        if not self._pdf_hazir():
            return
        hedef = self._yeni_dosya_adi(self.m("temiz_ek"))
        try:
            with self._taze_kopya() as kopya:
                bilgi = kopya.metadata or {}
                bulunan = [a for a in self.USTVERI_ALANLARI if str(bilgi.get(a) or "").strip()]
                xmp = bool((kopya.get_xml_metadata() or "").strip())
                # Yorum yazari /T anahtarinda. set_info(title="") bos degeri
                # yok sayiyor, anahtar nesneden silinir. Form alanlari (widget)
                # atlanir: onlarda /T alanin adi, silinirse form bozulur.
                yazarlar = 0
                for sayfa in kopya:
                    for xref, tur, _ in sayfa.annot_xrefs():
                        if tur != pymupdf.PDF_ANNOT_WIDGET and \
                                kopya.xref_get_key(xref, "T")[0] != "null":
                            kopya.xref_set_key(xref, "T", "null")
                            yazarlar += tur != pymupdf.PDF_ANNOT_POPUP
                if not (bulunan or xmp or yazarlar):
                    self.bildir(self.m("ustveri_yok"), "vurgu")
                    return
                kopya.set_metadata({})
                if xmp:
                    kopya.del_xml_metadata()
                kopya.save(hedef, garbage=4, deflate=True)
        except Exception as e:
            self.bildir(self.m("yazilamadi", e=e), "hata")
            return
        alanlar = [self.m(f"alan_{a}") for a in bulunan]
        if xmp:
            alanlar.append(self.m("alan_xmp"))
        if yazarlar:
            alanlar.append(self.m("alan_yorum_yazari", n=yazarlar))
        self.bildir(self.m("ustveri_silindi", alanlar=", ".join(alanlar),
                           ad=os.path.basename(hedef)), "vurgu")

    # -- karartma (X) --------------------------------------------------------
    #
    # Kalem acikken surukleme kutu, tik altindaki kelimeyi isaretler;
    # `:karart <kelime>` belgedeki her gecisi. Isaretler yalnizca bellekte ve
    # ekranda (siyah taramali kutu - altindakinin dogru sey oldugu gorulsun).
    # Enter / karartmayi-uygula taze kopyada apply_redactions calistirir:
    # metin, gorsel pikselleri ve cizgiler **gercekten silinir**, yerine siyah
    # kutu kalir. Ustune siyah dikdortgen cizmek degil - alttaki metin
    # kopyalanamaz. Yazdiktan sonra dosya diskten yeniden okunup her alanda
    # metin kalmis mi bakilir. Ctrl-Z / U son isareti (ya da son aramanin
    # butun isaretlerini) geri alir.

    def karartma_kalemi_degistir(self) -> None:
        if not self._pdf_hazir():
            return
        if self.karartma_acik:
            self._karartma_kalemini_birak()
            self.tuval.config(cursor="")
            if self.karartmalar:
                self.bildir(self.m("karartma_bekliyor", n=len(self.karartmalar)), "uyari")
            else:
                self.bildir(self.m("karartma_kapali"), "vurgu")
            return
        self._karartma_kalemini_al()
        self.bildir(self.m("karartma_acik"), "uyari")

    def _karartma_kalemini_al(self) -> None:
        self.kalem = False                  # ayni anda tek kalem
        self._silme_kipini_kapat()
        self.karartma_acik = True
        self.tuval.config(cursor="crosshair")

    def _karartma_kalemini_birak(self) -> None:
        """Kalemi indirir; isaretler durur (Enter / karartmayi-uygula yazar)."""
        self.karartma_acik = False
        self._karartma_cizimi = None
        self.tuval.delete("karartma-surukle")

    def _karartma_basla(self, x: float, y: float) -> None:
        yer = self._noktadaki_sayfa(x, y)
        if not yer:
            self.bildir(self.m("not_sayfa_disi"), "uyari")
            return
        self._karartma_cizimi = {"yer": yer, "x0": x, "y0": y, "x1": x, "y1": y}

    def _karartma_surukle(self, x: float, y: float) -> None:
        c = self._karartma_cizimi
        yer = c["yer"]                      # kutu tek sayfada kalir
        c["x1"] = max(yer["x"], min(yer["x"] + yer["w"], x))
        c["y1"] = max(yer["y"], min(yer["y"] + yer["h"], y))
        self.tuval.delete("karartma-surukle")
        self.tuval.create_rectangle(c["x0"], c["y0"], c["x1"], c["y1"], outline=self.ayar["hata"],
                                    dash=(4, 2), tags=("karartma-surukle",))

    def _karartma_bitir(self) -> None:
        c, self._karartma_cizimi = self._karartma_cizimi, None
        self.tuval.delete("karartma-surukle")
        yer = c["yer"]
        if abs(c["x1"] - c["x0"]) + abs(c["y1"] - c["y0"]) <= 4:     # tik: altindaki kelime
            p = self._sayfa_noktasina(yer, c["x0"], c["y0"])
            kelime = next((k for k in self._sayfa_kelimeleri(yer["no"])
                           if pymupdf.Rect(k[:4]).contains(p)), None)
            if kelime is None:
                self.bildir(self.m("karartma_kelime_yok"), "uyari")
                return
            dik = pymupdf.Rect(kelime[:4])
        else:
            dik = pymupdf.Rect(self._sayfa_noktasina(yer, c["x0"], c["y0"]),
                               self._sayfa_noktasina(yer, c["x1"], c["y1"]))
            dik.normalize()
        self._karartma_isaretle([{"sayfa": yer["no"], "dik": [round(v, 2) for v in dik]}])
        self.bildir(self.m("karartma_eklendi", n=len(self.karartmalar)), "uyari")

    def _karartma_isaretle(self, yeni: list[dict]) -> None:
        self.karartmalar.extend(yeni)
        self.geri_yigini.append(("karartma-ekle", yeni, None))   # U / Ctrl-Z topluca geri alir
        self.karartmalari_ciz()

    def karart_ara(self, desen: str) -> None:
        """`:karart <kelime>`: her gecisi isaretler ve kalemi acar; Enter yazar.
        Buyuk / kucuk harf ayrilmaz (MuPDF'in aramasi). Tarama `/` gibi
        parca parca yurur: 1612 sayfalik kitapta tek seferde ~10 sn donuyordu."""
        if not self._pdf_hazir():
            return
        desen = desen.strip()
        if not desen:
            self.bildir(self.m("karart_kullanim"), "uyari")
            return
        self._karart_isi = {"desen": desen, "belge": self.belge, "no": 0, "yeni": []}
        self._karart_adimi(self._karart_isi)

    def _karart_adimi(self, isi: dict) -> None:
        # Belge degistiyse ya da yeni bir :karart basladiysa bu is biter.
        if isi is not self._karart_isi or isi["belge"] is not self.belge:
            return
        toplam = self.belge.page_count
        bitis = time.perf_counter() + 0.04
        while isi["no"] < toplam and time.perf_counter() < bitis:
            no = isi["no"]
            isi["yeni"] += [{"sayfa": no, "dik": [round(v, 2) for v in d]}
                            for d in self.belge[no].search_for(isi["desen"])]
            isi["no"] += 1
        if isi["no"] < toplam:
            self.bildir(self.m("karart_araniyor", desen=isi["desen"], n=isi["no"],
                               toplam=toplam), "uyari")
            self.after(1, self._karart_adimi, isi)
            return
        self._karart_isi = None
        if not isi["yeni"]:
            self.bildir(self.m("eslesme_yok"), "uyari")
            return
        self._karartma_kalemini_al()
        self._karartma_isaretle(isi["yeni"])
        self.bildir(self.m("karart_bulundu", desen=isi["desen"], n=len(isi["yeni"])), "uyari")

    def karartmalari_ciz(self, gorunur: set[int] | None = None) -> None:
        self.tuval.delete("karartma")
        if not self.karartmalar:
            return
        if gorunur is None:                 # ciz() disindan: yalnizca islenmis sayfalar
            gorunur = set(self.tuval_ogeleri)
        m = self.sayfa_matrisi()
        for k in self.karartmalar:
            no = int(k["sayfa"])
            yer = self.sayfa_yeri(no) if no in gorunur else None
            if not yer:
                continue
            x0, y0, x1, y1 = self.aygit_dikdortgeni(no, pymupdf.Rect(k["dik"]), yer, m)
            self.tuval.create_rectangle(x0, y0, x1, y1, fill="#000000", stipple="gray75",
                                        outline=self.ayar["hata"], tags=("karartma",))

    def karartmayi_uygula(self) -> None:
        if not self._pdf_hazir():
            return
        if not self.karartmalar:
            self.bildir(self.m("karartma_yok"), "uyari")
            return
        isaretler = list(self.karartmalar)
        hedef = self._yeni_dosya_adi(self.m("karartilmis_ek"))
        try:
            with self._taze_kopya() as kopya:
                for k in isaretler:
                    kopya[int(k["sayfa"])].add_redact_annot(pymupdf.Rect(k["dik"]), fill=(0, 0, 0))
                for no in sorted({int(k["sayfa"]) for k in isaretler}):
                    kopya[no].apply_redactions()
                kopya.save(hedef, garbage=4, deflate=True, clean=True)
            sizan = self._karartma_sizan(hedef, isaretler)
        except Exception as e:
            self.bildir(self.m("yazilamadi", e=e), "hata")
            return
        self.karartmalar = []
        self._karartma_kalemini_birak()
        self.tuval.config(cursor="")
        ad = os.path.basename(hedef)
        self.belgeyi_ac(hedef)              # sonucu hemen gor
        if sizan:
            self.bildir(self.m("karartma_sizdi", n=sizan, ad=ad), "hata")
        else:
            self.bildir(self.m("karartildi", n=len(isaretler), ad=ad), "vurgu")

    @staticmethod
    def _karartma_sizan(yol: str, isaretler: list[dict]) -> int:
        """Yazilan dosyada icinde hala metin okunan isaretli alan sayisi. Alan
        1 pt iceriden okunur: kenara degen komsu harf sizinti sayilmasin."""
        sizan = 0
        with pymupdf.open(yol) as belge:
            for k in isaretler:
                d = pymupdf.Rect(k["dik"])
                if d.width > 2 and d.height > 2:
                    d = d + (1, 1, -1, -1)
                if belge[int(k["sayfa"])].get_text("text", clip=d).strip():
                    sizan += 1
        return sizan

    # -- sayfa duzeni (S) ----------------------------------------------------
    #
    # Belgenin ustune binen kucuk resim izgarasi. hjkl gezer, HJKL imlecteki
    # sayfayi (ya da v ile secilen araligi) tasir, x siler, r / R saga / sola
    # dondurur, u geri alir, e secileni ayri bir PDF'e yazar, w butun duzeni
    # yeni dosyaya yazip onu acar, q / Esc kapatir - kaydedilmemis degisiklik
    # varsa ikinci q ister. Fare: tik secer, Shift+tik araligi secer.
    #
    # Duzen yalnizca bir liste: [kaynak sayfa, ek donme]. Yazana kadar belgeye
    # dokunulmaz; yazarken taze kopyada select() + set_rotation. Kucuk resimler
    # notsuz (annots=False) islenir: ciktida vurgu olmayacak, burada da yok.
    #
    # Izgara tam sayi pikselde (bkz. CLAUDE.md "piksel izgarasi"): hucre ve
    # bosluk sabit, kaydirma kendi ofsetiyle; tuvalin scrollregion'i yok.

    DUZEN_KUTU = (132, 172)             # kucuk resmin sigdigi kutu (px)
    DUZEN_ARA = 18                      # hucreler arasi bosluk (px)
    DUZEN_ETIKET = 20                   # resmin altindaki numara satiri (px)
    DUZEN_UST = 30                      # ustteki baslik satiri (px)
    DUZEN_ONBELLEK = 400                # en cok bu kadar kucuk resim tutulur

    def sayfa_duzeni(self) -> None:
        if not self._pdf_hazir():
            return
        if self.mod in ("icindekiler", "vurgular", "belgeler", "yer-imleri"):
            self.paneli_kapat()
        if not hasattr(self, "duzen_tuvali"):
            self.duzen_tuvali = tk.Canvas(self, bd=0, highlightthickness=0, takefocus=1)
            self.duzen_tuvali.bind("<Configure>", self._duzen_olcu_degisti)
            self.duzen_tuvali.bind("<ButtonPress-1>", self._duzen_tik)
            self.duzen_tuvali.bind("<MouseWheel>", self._duzen_tekerlek)
        n = self.belge.page_count
        self._duzen = {"belge": self.belge, "yol": self.pdf_yolu,
                       "sira": [[no, 0] for no in range(n)],
                       "imlec": max(0, min(self.aktif_sayfa, n - 1)), "capa": None,
                       "gecmis": [], "resimler": {}, "ust": 0, "q_bekliyor": False}
        self.mod = "sayfa-duzeni"
        self.duzen_tuvali.config(bg=self.ayar["zemin"])
        self.duzen_tuvali.place(in_=self.tuval_alani, x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self.duzen_tuvali)     # Canvas.lift tag_raise'dir, pencereyi degil
        self.duzen_tuvali.focus_set()
        self.update_idletasks()
        self._duzen_imleci_goster()
        self._duzeni_ciz()
        self.gecici_ileti = ""              # onceki isin iletisi yerine tus ipucu
        self._duzen_ipucu()

    def _duzen_ipucu(self) -> None:
        """Tus ipucu durum cubugunda durur (baslik satirina 1100 px'te bile
        sigmiyordu); bir islemin iletisi varsa bir sonraki tusa kadar o."""
        if not self.gecici_ileti:
            self.bildir(self.m("duzen_ipucu"), "sonuk")

    def _duzeni_kapat(self) -> None:
        self.duzen_tuvali.place_forget()
        self.duzen_tuvali.delete("all")
        self._duzen = None                  # kucuk resimler de gider
        self.mod = "normal"
        self.gecici_ileti = ""              # tus ipucu belgenin ustunde kalmasin
        self.tuval.focus_set()
        self.durumu_tazele()

    def _duzen_olcusu(self) -> tuple[int, int, int, int]:
        """(sutun sayisi, sol pay, hucre eni, hucre boyu) - hepsi tam sayi."""
        kw, kh = self.DUZEN_KUTU
        hw, hh = kw + self.DUZEN_ARA, kh + self.DUZEN_ETIKET + self.DUZEN_ARA
        en = max(1, self.duzen_tuvali.winfo_width())
        sutun = max(1, (en - self.DUZEN_ARA) // hw)
        return sutun, (en - sutun * hw + self.DUZEN_ARA) // 2, hw, hh

    def _duzen_hucresi(self, i: int) -> tuple[int, int]:
        """i. hucrenin resim kutusunun sol ustu, tuvalde (kaydirma uygulanmis)."""
        sutun, sol, hw, hh = self._duzen_olcusu()
        return (sol + (i % sutun) * hw,
                self.DUZEN_UST + self.DUZEN_ARA + (i // sutun) * hh - self._duzen["ust"])

    def _duzen_ofsetini_sinirla(self) -> None:
        d = self._duzen
        sutun, _, _, hh = self._duzen_olcusu()
        boy = self.duzen_tuvali.winfo_height() - self.DUZEN_UST
        toplam = self.DUZEN_ARA + -(-len(d["sira"]) // sutun) * hh
        d["ust"] = max(0, min(d["ust"], toplam - boy))

    def _duzen_imleci_goster(self) -> None:
        d = self._duzen
        sutun, _, _, hh = self._duzen_olcusu()
        boy = self.duzen_tuvali.winfo_height() - self.DUZEN_UST
        ust = (d["imlec"] // sutun) * hh            # imlec satiri, izgara uzayinda
        if ust < d["ust"]:
            d["ust"] = ust
        elif ust + hh + self.DUZEN_ARA > d["ust"] + boy:
            d["ust"] = ust + hh + self.DUZEN_ARA - boy
        self._duzen_ofsetini_sinirla()

    def _duzen_secili(self) -> range:
        d = self._duzen
        if d["capa"] is None:
            return range(d["imlec"], d["imlec"] + 1)
        a, b = sorted((d["capa"], d["imlec"]))
        return range(a, b + 1)

    def _duzen_degisti(self) -> bool:
        d = self._duzen
        return d["sira"] != [[no, 0] for no in range(d["belge"].page_count)]

    def _duzen_resmi(self, kaynak: int, donme: int) -> tk.PhotoImage | None:
        resimler = self._duzen["resimler"]
        anahtar = (kaynak, donme)
        resim = resimler.pop(anahtar, None)
        if resim is None:
            try:
                sayfa = self._duzen["belge"][kaynak]
                r = sayfa.rect
                w, h = (r.height, r.width) if donme % 180 else (r.width, r.height)
                kw, kh = self.DUZEN_KUTU
                k = min(kw / max(w, 1), kh / max(h, 1))
                m = pymupdf.Matrix(k, k)
                m.prerotate(donme)
                pix = sayfa.get_pixmap(matrix=m, alpha=False, annots=False)
                resim = tk.PhotoImage(master=self, data=pix.tobytes("ppm"))
            except Exception:
                return None
        resimler[anahtar] = resim           # en sona: en son kullanilan
        while len(resimler) > self.DUZEN_ONBELLEK:
            del resimler[next(iter(resimler))]
        return resim

    def _duzeni_ciz(self) -> None:
        d, t = self._duzen, self.duzen_tuvali
        t.delete("all")
        sutun, _, _, hh = self._duzen_olcusu()
        kw, kh = self.DUZEN_KUTU
        en, boy = t.winfo_width(), t.winfo_height()
        yazi = (self.ayar["yazitipi"], max(8, int(self.ayar["yazitipi-boy"])))
        secim = self._duzen_secili() if d["capa"] is not None else range(0)
        alt = kh + self.DUZEN_ETIKET                # hucre cercevesinin alt payi
        for i in range(max(0, d["ust"] // hh * sutun), len(d["sira"])):
            x, y = self._duzen_hucresi(i)
            if y > boy:
                break
            kaynak, donme = d["sira"][i]
            if i in secim:
                t.create_rectangle(x - 6, y - 6, x + kw + 5, y + alt + 1,
                                   fill=self.ayar["panel-secili"], outline="")
            resim = self._duzen_resmi(kaynak, donme)
            if resim is not None:
                rw, rh = resim.width(), resim.height()
                ix, iy = x + (kw - rw) // 2, y + (kh - rh) // 2
                t.create_image(ix, iy, image=resim, anchor="nw")
                t.create_rectangle(ix - 1, iy - 1, ix + rw, iy + rh,
                                   outline=self.ayar["sayfa-cerceve"])
            imlecte = i == d["imlec"]
            t.create_text(x + kw // 2, y + kh + 4, anchor="n", font=yazi,
                          text=f"{kaynak + 1}" + (f" r{donme}" if donme else ""),
                          fill=self.ayar["vurgu"] if imlecte else self.ayar["sonuk"])
            if imlecte:
                t.create_rectangle(x - 6, y - 6, x + kw + 5, y + alt + 1,
                                   outline=self.ayar["vurgu"], width=2)
        # baslik satiri: izgaranin ustune, kaydirilan hucreleri ortsun
        t.create_rectangle(0, 0, en, self.DUZEN_UST - 1, fill=self.ayar["cubuk-zemin"], outline="")
        t.create_line(0, self.DUZEN_UST - 1, en, self.DUZEN_UST - 1,
                      fill=self.ayar["palet-cerceve"])
        baslik = self.m("duzen_baslik", ad=os.path.basename(d["yol"]),
                        n=self.m("sayfa_n", n=len(d["sira"])))
        if self._duzen_degisti():
            baslik += "  " + self.m("duzen_degisti")
        t.create_text(10, self.DUZEN_UST // 2, anchor="w", font=yazi, text=baslik,
                      fill=self.ayar["cubuk-on"])

    def duzen_tus(self, ad: str) -> None:
        d = self._duzen
        sutun, _, _, hh = self._duzen_olcusu()
        n = len(d["sira"])
        q_bekliyor, d["q_bekliyor"] = d["q_bekliyor"], False
        ekran = max(1, (self.duzen_tuvali.winfo_height() - self.DUZEN_UST) // hh) * sutun
        adim = {"h": -1, "<Left>": -1, "l": 1, "<Right>": 1, "k": -sutun, "<Up>": -sutun,
                "j": sutun, "<Down>": sutun, "<Prior>": -ekran, "<Next>": ekran}.get(ad)
        tasima = {"H": -1, "L": 1, "K": -sutun, "J": sutun}.get(ad)
        if adim is not None:
            d["imlec"] = max(0, min(n - 1, d["imlec"] + adim))
        elif ad in ("g", "<Home>"):
            d["imlec"] = 0
        elif ad in ("G", "<End>"):
            d["imlec"] = n - 1
        elif tasima is not None:
            self._duzen_tasi(tasima)
        elif ad in ("x", "d", "<Delete>"):
            self._duzen_sil()
        elif ad in ("r", "R"):
            self._duzen_dondur(90 if ad == "r" else 270)
        elif ad == "v":
            d["capa"] = d["imlec"] if d["capa"] is None else None
        elif ad in ("u", "U", "<C-z>"):
            self._duzen_geri_al()
        elif ad == "e":
            self._duzen_yaz(ayir=True)
        elif ad in ("w", "<C-s>"):
            if self._duzen_yaz():
                return                              # yazildi, duzen kapandi
        elif ad == "<Esc>" and d["capa"] is not None:
            d["capa"] = None
        elif ad in ("q", "<Esc>", "S"):
            if self._duzen_degisti() and not q_bekliyor:
                d["q_bekliyor"] = True
                self.bildir(self.m("duzen_kaydedilmedi"), "uyari")
            else:
                self._duzeni_kapat()
            return
        else:
            self._duzen_ipucu()
            return
        self._duzen_imleci_goster()
        self._duzeni_ciz()
        self._duzen_ipucu()

    def _duzen_gecmise(self) -> None:
        d = self._duzen
        d["gecmis"].append(([s[:] for s in d["sira"]], d["imlec"], d["capa"]))

    def _duzen_tasi(self, adim: int) -> None:
        d = self._duzen
        blok = self._duzen_secili()
        a = blok.start
        yeni = max(0, min(len(d["sira"]) - len(blok), a + adim))
        if yeni == a:
            return
        self._duzen_gecmise()
        parca = d["sira"][blok.start:blok.stop]
        del d["sira"][blok.start:blok.stop]
        d["sira"][yeni:yeni] = parca
        d["imlec"] += yeni - a
        if d["capa"] is not None:
            d["capa"] += yeni - a

    def _duzen_sil(self) -> None:
        d = self._duzen
        blok = self._duzen_secili()
        if len(blok) >= len(d["sira"]):
            self.bildir(self.m("duzen_hepsi"), "uyari")
            return
        self._duzen_gecmise()
        del d["sira"][blok.start:blok.stop]
        d["imlec"] = min(blok.start, len(d["sira"]) - 1)
        d["capa"] = None
        self.bildir(self.m("duzen_silindi", sayfalar=self.m("sayfa_n", n=len(blok))), "vurgu")

    def _duzen_dondur(self, derece: int) -> None:
        self._duzen_gecmise()
        for i in self._duzen_secili():
            s = self._duzen["sira"][i]
            s[1] = (s[1] + derece) % 360

    def _duzen_geri_al(self) -> None:
        d = self._duzen
        if not d["gecmis"]:
            self.bildir(self.m("duzen_geri_yok"), "uyari")
            return
        d["sira"], d["imlec"], d["capa"] = d["gecmis"].pop()

    def _duzen_yaz(self, ayir: bool = False) -> bool:
        """w: butun duzeni yazar ve yeni dosyayi acar (duzen kapanir, True).
        e: yalnizca secili sayfalari yazar, duzende kalinir."""
        d = self._duzen
        if ayir:
            sira, ek = [d["sira"][i] for i in self._duzen_secili()], self.m("ayri_ek")
        elif not self._duzen_degisti():
            self.bildir(self.m("duzen_degismedi"), "uyari")
            return False
        else:
            sira, ek = d["sira"], self.m("duzen_ek")
        hedef = self._yeni_dosya_adi(ek)
        try:
            with pymupdf.open(d["yol"]) as kopya:
                kopya.select([k for k, _ in sira])
                for i, (_, donme) in enumerate(sira):
                    if donme:
                        kopya[i].set_rotation((kopya[i].rotation + donme) % 360)
                kopya.save(hedef, garbage=3, deflate=True)
        except Exception as e:
            self.bildir(self.m("yazilamadi", e=e), "hata")
            return False
        ileti = self.m("duzen_yazildi", sayfalar=self.m("sayfa_n", n=len(sira)),
                       ad=os.path.basename(hedef))
        if ayir:
            self.bildir(ileti, "vurgu")
            return False
        self._duzeni_kapat()
        self.belgeyi_ac(hedef)
        self.bildir(ileti, "vurgu")
        return True

    def _duzen_olcu_degisti(self, _olay=None) -> None:
        if self.mod == "sayfa-duzeni":
            self._duzen_imleci_goster()
            self._duzeni_ciz()

    def _duzen_tik(self, olay) -> None:
        d = self._duzen
        if d is None:
            return
        self.duzen_tuvali.focus_set()
        sutun, sol, hw, hh = self._duzen_olcusu()
        gy = olay.y - self.DUZEN_UST - self.DUZEN_ARA // 2 + d["ust"]
        sutun_no = (olay.x - sol + self.DUZEN_ARA // 2) // hw
        if olay.y < self.DUZEN_UST or gy < 0 or not 0 <= sutun_no < sutun:
            return
        i = gy // hh * sutun + sutun_no
        if i >= len(d["sira"]):
            return
        if olay.state & 0x1:                        # Shift+tik: araligi sec
            if d["capa"] is None:
                d["capa"] = d["imlec"]
        else:
            d["capa"] = None
        d["imlec"] = i
        d["q_bekliyor"] = False
        self._duzeni_ciz()

    def _duzen_tekerlek(self, olay) -> None:
        if self._duzen is None:
            return
        self._duzen["ust"] -= int(olay.delta / 120 * self._duzen_olcusu()[3] / 2)
        self._duzen_ofsetini_sinirla()
        self._duzeni_ciz()

    # -- icindekiler -------------------------------------------------------

    def icindekiler(self) -> None:
        if not self.belge or self._panel_kapandi("icindekiler"):
            return
        toc = self.belge.get_toc()
        if not toc:
            self.bildir(self.m("icindekiler_yok"), "uyari")
            return
        self.icindekiler_verisi = [max(0, sayfa - 1) for _, _, sayfa in toc]
        self._paneli_ac("icindekiler",
                        [f"{'  ' * max(0, derinlik - 1)}{'+ ' if derinlik == 1 else '- '}"
                         f"{baslik}  [{sayfa}]" for derinlik, baslik, sayfa in toc],
                        self._icindekiler_baslangici())

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

    def _panel_kapandi(self, mod: str) -> bool:
        """Panel tuslari ac/kapa: bu panel zaten aciksa kapatir, True doner."""
        if self.mod == mod:
            self.paneli_kapat()
            return True
        return False

    def _paneli_ac(self, mod: str, satirlar: list[str], secim: int) -> None:
        """Icindekiler, vurgular ve belgeler ayni listeyi kullanir."""
        self.liste.delete(0, "end")
        self.liste.insert("end", *satirlar)
        self.mod = mod
        self.panel.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.liste.focus_set()
        self._panel_satiri_sec(secim)
        self.durumu_tazele()

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
        elif ad in ("x", "<Delete>") and self.mod == "yer-imleri":
            self.listeden_yer_imi_sil()
        elif ad == "a" and self.mod == "yer-imleri":
            self.paneli_kapat()
            self.yer_imi_koy()
            self.yer_imi_listesi()
        elif ad == "b" and self.mod == "yer-imleri":
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
        elif self.mod == "yer-imleri":
            im = self.panel_konumlari[secili[0]]
            self.paneli_kapat()
            self.zipla_kaydet()                 # <C-o> geri getirir
            self.konum_imine_git((im["sayfa"], im["oran"]))
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
        if self.mod in ("icindekiler", "vurgular", "belgeler", "yer-imleri"):
            self.paneli_kapat()
        elif self.mod in ("komut", "arama"):
            self.komut_iptal()

        self.palet_desen.set("")        # mod henuz palet degil: izleyici doldurmaz
        self.mod = "palet"
        self.palet_kip = "liste"
        self.palet_hedef = ""
        self.palet_yeni_tus = ""
        self.palet_secim = 0
        self.palet.place(relx=0.5, rely=0.5, anchor="center",
                         relwidth=0.82, relheight=0.76)
        self.palet.lift()
        self.palet_girdi.focus_set()
        self.update_idletasks()         # genisligi olcebilmek icin yerlessin
        self._palet_genisligini_olc()
        self.palet_doldur()
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

    def _palet_satiri(self, komut: str, aciklama: str, tuslar: str, sutun: int) -> str:
        """`komut` ic kimlik; satira secili dildeki adi yazilir, `sutun` genisliginde."""
        en = self._palet_en
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
        # Ad sutunu o dilin en uzun adina gore (Almanca "markierungen-exportieren" 24 harf)
        sutun = max([len(a) for a in KOMUT_ADLARI.get(dil, {}).values()] + [22]) + 2
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
                self._palet_ekle(self._palet_satiri(komut, metin, tuslar, sutun), komut)

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
        if komut in ("dil", "tema", "geri-acma-siniri", "yazici", "vurgu-renkleri"):
            self.komutlar[komut]()      # palet kapanmasin: secim listesi yerinde acilir
            return
        self.paleti_kapat()
        self.calistir(komut)

    def palet_fare(self, olay) -> str:
        if self.palet_kip == "liste":
            self.palet_sec(self.palet_liste.nearest(olay.y), 1)
        self.palet_girdi.focus_set()
        return "break"      # listbox odagi kapmasin, tuslar girdide kalsin

    def palet_ipucunu_tazele(self) -> None:
        kip = {"renk-yakala": "yakala", "renk-onay": "onay"}.get(self.palet_kip, self.palet_kip)
        if kip in SECIM_KIPLERI and kip != "renk":
            kip = "eylem"
        self.palet_ipucu.config(text=self.m(f"ipucu_{kip}"))

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
        self._alt_sec(0)
        self.alt_menu.place(relx=1.0, rely=1.0, x=-12, y=-34, anchor="se")
        self.alt_menu.lift()
        self.palet_ipucunu_tazele()

    def alt_menuyu_kapat(self) -> None:
        self.alt_menu.place_forget()
        self.alt_ogeleri = []
        if self.palet_kip in ("eylem", "kaldir", *SECIM_KIPLERI):
            self.palet_kip = "liste"
        self.palet_ipucunu_tazele()

    def _alt_sec(self, i: int) -> None:
        self.alt_secim = i
        self.alt_liste.selection_clear(0, "end")
        self.alt_liste.selection_set(i)
        self.alt_liste.see(i)

    def alt_gez(self, yon: int) -> None:
        if self.alt_ogeleri:
            self._alt_sec(max(0, min(len(self.alt_ogeleri) - 1, self.alt_secim + yon)))

    def alt_fare(self, olay) -> str:
        i = self.alt_liste.nearest(olay.y)
        if 0 <= i < len(self.alt_ogeleri):
            self._alt_sec(i)
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

    def _secim_menusu(self, komut: str, kip: str, baslik: str,
                      secenekler: list[tuple], simdiki) -> None:
        """[x] / [ ] secim listesi (dil, tema, geri acma siniri). `secenekler`:
        (deger, etiket, sag yazi). Palet kapaliysa (`:lang`, tusa baglanmis
        komut) once acilir; secim paleti kapatmaz."""
        if self.mod != "palet":
            self.eylemler()
        self._palet_komuta_git(komut)
        ogeler = [d for d, _, _ in secenekler]
        self.palet_kip = kip
        self.alt_menu_ac(baslik, [(f"[{'x' if d == simdiki else ' '}] {etiket}", sag)
                                  for d, etiket, sag in secenekler], ogeler)
        if simdiki in ogeler:                   # imlec secili degerde baslasin
            self.alt_gez(ogeler.index(simdiki))

    def dil_menusu(self) -> None:
        """[x] English / [ ] Türkçe / [ ] Deutsch; liste hemen yeni dilde cizilir."""
        self._secim_menusu("dil", "dil", self.m("dil_baslik"),
                           [(kod, ad, kod) for kod, ad in DILLER.items()], self.ayar["dil"])

    def tema_menusu(self) -> None:
        """Her satir kendi temasinin vurgu renginde (menu zemininde okunuyorsa)."""
        self._secim_menusu("tema", "tema", self.m("tema_baslik"),
                           [(t, komut_adi(f"tema-{t}", self.ayar["dil"]), "") for t in TEMALAR],
                           self.ayar["tema"])
        for i, tema in enumerate(TEMALAR.values()):
            if kontrast(tema["vurgu"], self.ayar["panel-zemin"]) >= 3:
                self.alt_liste.itemconfig(i, foreground=tema["vurgu"])

    def sinir_menusu(self) -> None:
        """Geri acma siniri: [x] 1 belge ... [ ] 10 belge."""
        varsayilan = VARSAYILAN_AYAR["kapanan-belgeler"]
        self._secim_menusu("geri-acma-siniri", "sinir", self.m("sinir_baslik"),
                           [(n, f"{' ' if n < 10 else ''}{self.m('sinir_satir', n=n)}",
                             self.m("sinir_varsayilan") if n == varsayilan else "")
                            for n in range(1, KAPANAN_EN_COK + 1)],
                           self._kapanan_siniri())

    def yazici_menusu(self) -> None:
        """Kurulu yazicilar; ilk satir Windows'un varsayilanina birakir."""
        yazicilar = _yazicilar()
        varsayilan = _varsayilan_yazici()
        secenekler = [("", self.m("yazici_sistem"), varsayilan or self.m("yok"))]
        secenekler += [(y, y, self.m("sinir_varsayilan") if y == varsayilan else "")
                       for y in yazicilar]
        self._secim_menusu("yazici", "yazici", self.m("yazici_baslik"), secenekler,
                           str(self.ayar["yazdirma-yazicisi"]))

    def yaziciyi_ayarla(self, ad: str) -> None:
        """Ctrl-K > ayarlar > yazici. rubricrc'ye `set yazdirma-yazicisi` yazilir."""
        self.ayar["yazdirma-yazicisi"] = ad
        self.alt_menuyu_kapat()
        yazildi = self.rc_tus_yaz({}, ayarlar={"yazdirma-yazicisi": ad})
        self._kalici_bildir(self.m("yazici_secildi",
                                   ad=ad or _varsayilan_yazici() or self.m("yok")), yazildi)

    # -- palet: vurgu renkleri ---------------------------------------------
    #
    # Temalar gibi tek satir; Enter bos bir liste acar: yalnizca renkler ve
    # tuslari, her satir kendi renginde. Bir rengin uzerinde Enter o rengin
    # tusunu sorar (tus atamayla ayni ekran), onay `set vurgu-tuslari` olarak
    # rubricrc'ye yazilir. Tuslar yalnizca secim renk beklerken gecerli
    # (bkz. tus_geldi), bu yuzden normal tuslarla catismazlar.

    def vurgu_renk_menusu(self, secili: str | None = None) -> None:
        if self.mod != "palet":
            self.eylemler()
        self._palet_komuta_git("vurgu-renkleri")
        tuslar: dict[str, list[str]] = {}
        for tus, renk in self.renk_tuslari().items():
            tuslar.setdefault(renk, []).append(tus)
        ogeler = list(VURGU_RENKLERI)
        varsayilan = self.vurgu_varsayilani()
        satirlar = []
        for renk in ogeler:
            sag = "  ".join(tuslar.get(renk, []))
            ad = self.renk_adi(renk)
            if renk == "sari":
                ad += f"  ({self.m('renk_tema')})"
            if renk == varsayilan:
                ad += f"  ({self.m('sinir_varsayilan')})"
                sag = f"{sag}  enter".strip()
            satirlar.append((ad, sag or "-"))
        self.palet_kip = "renk"
        self.alt_menu_ac(self.m("renk_baslik"), satirlar, ogeler)
        for i, renk in enumerate(ogeler):
            renk_hex = VURGU_RENKLERI[renk] or self.ayar["vurgu-rengi"]
            if kontrast(renk_hex, self.ayar["panel-zemin"]) >= 3:
                self.alt_liste.itemconfig(i, foreground=renk_hex)
        if secili in ogeler:
            self.alt_gez(ogeler.index(secili))

    def vurgu_varsayilanini_ata(self, renk: str) -> None:
        """Ctrl-K > vurgu renkleri > bosluk: Enter'in koydugu rengi degistirir."""
        if renk not in VURGU_RENKLERI:
            return
        self.ayar["vurgu-varsayilan"] = renk
        yazildi = self.rc_tus_yaz({}, ayarlar={"vurgu-varsayilan": renk})
        self.vurgu_renk_menusu(renk)            # liste isareti yeni renge gecsin
        self._kalici_bildir(self.m("renk_varsayilan_atandi", renk=self.renk_adi(renk)),
                            yazildi)

    def renk_tusu_sor(self, renk: str) -> None:
        self.alt_menu.place_forget()
        self.alt_ogeleri = []
        self.palet_hedef = renk
        self.palet_yeni_tus = ""
        self.palet_kip = "renk-yakala"
        self.renk_yakala_goster()

    @staticmethod
    def _renk_tusu_olmaz(tus: str) -> bool:
        """Enter varsayilan rengi koyar, Esc secimi birakir; `#` rubricrc'de
        bosluktan sonra gelince yorum sayilir (set vurgu-tuslari ... #:mavi)."""
        return tus in ("<Return>", "<Esc>") or tus.startswith("#") or not tus.strip()

    def renk_uyarisi(self, tus: str) -> str:
        if self._renk_tusu_olmaz(tus):
            return self.m("renk_tusu_olmaz", tus=tus)
        sahip = self.renk_tuslari().get(tus)
        if sahip == self.palet_hedef:
            return self.m("renk_zaten", tus=tus, renk=self.renk_adi(sahip))
        if sahip:
            return self.m("renk_catisma", tus=tus, renk=self.renk_adi(sahip))
        return ""

    def renk_yakala_goster(self) -> None:
        renk = self.palet_hedef
        renk_hex = VURGU_RENKLERI.get(renk) or self.ayar["vurgu-rengi"]
        ust_rengi = renk_hex if kontrast(renk_hex, self.ayar["panel-secili"]) >= 3 \
            else self.ayar["vurgu"]
        simdiki = "  ".join(t for t, r in self.renk_tuslari().items() if r == renk) \
            or self.m("yok")
        if self.palet_kip == "renk-yakala":
            self.yakala_ust.config(text=f"{self.renk_adi(renk)}  <-  ___", fg=ust_rengi)
            self.yakala_orta.config(text=self.m("simdiki_tuslar", tuslar=simdiki),
                                    fg=self.ayar["sonuk"])
            self.yakala_alt.config(text=self.m("yakala_bekle"))
        else:
            self.yakala_ust.config(text=f"{self.renk_adi(renk)}  <-  {self.palet_yeni_tus}",
                                   fg=ust_rengi)
            self.yakala_orta.config(text=self.renk_uyarisi(self.palet_yeni_tus),
                                    fg=self.ayar["uyari"])
            self.yakala_alt.config(text=self.m("yakala_onay"))
        self.yakala.place(relx=0.5, rely=0.5, anchor="center")
        self.yakala.lift()
        self.palet_ipucunu_tazele()

    def renk_yakala_tus(self, ad: str) -> str:
        if not ad:
            return "break"
        if ad == "<Esc>":
            self._renk_yakalamayi_bitir()
            self.bildir(self.m("atama_iptal"), "uyari")
            return "break"
        if self.palet_kip == "renk-onay" and ad == "<Return>":
            self.renk_tusunu_uygula()
            return "break"
        self.palet_yeni_tus = ad
        self.palet_kip = "renk-onay"
        self.renk_yakala_goster()
        return "break"

    def _renk_yakalamayi_bitir(self) -> None:
        renk = self.palet_hedef
        self.yakala.place_forget()
        self.palet_kip = "liste"
        self.palet_yeni_tus = ""
        self.palet_girdi.focus_set()
        self.vurgu_renk_menusu(renk)            # liste, imlec ayni renkte, geri gelir

    def renk_tusunu_uygula(self) -> None:
        tus, renk = self.palet_yeni_tus, self.palet_hedef
        if not tus or renk not in VURGU_RENKLERI:
            self._renk_yakalamayi_bitir()
            return
        if self._renk_tusu_olmaz(tus):
            self.bildir(self.renk_uyarisi(tus), "uyari")
            return                              # onay ekraninda kal, baska tusa basilabilir
        eski = self.renk_tuslari()
        onceki = eski.get(tus)
        # bir rengin tek tusu olur; alinan tus eski renginden duser
        yeni = {t: r for t, r in eski.items() if r != renk and t != tus}
        yeni[tus] = renk
        sira = list(VURGU_RENKLERI)
        deger = " ".join(f"{t}:{r}" for t, r in sorted(yeni.items(),
                                                       key=lambda tr: sira.index(tr[1])))
        self.ayar["vurgu-tuslari"] = deger
        yazildi = self.rc_tus_yaz({}, ayarlar={"vurgu-tuslari": deger})
        self._renk_yakalamayi_bitir()
        alinan = self.m("alindi_ek", onceki=self.renk_adi(onceki)) \
            if onceki and onceki != renk else ""
        self._kalici_bildir(self.m("renk_atandi", renk=self.renk_adi(renk), tus=tus) + alinan,
                            yazildi)

    def alt_onayla(self) -> None:
        if not (0 <= self.alt_secim < len(self.alt_ogeleri)):
            return
        secim, kip = self.alt_ogeleri[self.alt_secim], self.palet_kip
        if kip == "kaldir":
            self.tusu_kaldir_uygula(secim)
        elif kip in SECIM_KIPLERI:
            self.alt_menuyu_kapat()
            {"dil": self.dili_ayarla, "tema": self.tema_uygula,
             "sinir": self.kapanan_siniri_ayarla, "renk": self.renk_tusu_sor,
             "yazici": self.yaziciyi_ayarla}[kip](secim)
        else:
            {"calistir": self.palet_calistir, "tus-ata": self.tus_ata,
             "tus-kaldir": self.tusu_kaldir, "varsayilan": self.varsayilana_don}[secim]()

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
        self.yakala_ust.config(fg=self.ayar["vurgu"])     # renk yakalama boyamis olabilir
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
        self._kalici_bildir(f"map {tus} {komut}{alinan}", yazildi)

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
        self._kalici_bildir(f"unmap {tus}", yazildi)

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
        self._kalici_bildir(self.m("varsayilana_dondu", komut=self.ad(komut), tuslar=geri), yazildi)

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
        if kip in ("renk-yakala", "renk-onay"):
            return self.renk_yakala_tus(ad)

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
        if ad == "<Space>" and kip == "renk":
            if 0 <= self.alt_secim < len(self.alt_ogeleri):
                self.vurgu_varsayilanini_ata(self.alt_ogeleri[self.alt_secim])
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

    def not_modu(self, metin: str = "") -> None:
        """Komut satirini not yazmak icin acar. Onek yok: yazilan her sey
        notun kendisi, `:` ya da `/` ile baslayan bir not da yazilabilsin."""
        self.mod = "not"
        self.komut_girdi.pack(side="bottom", fill="x", before=self.cubuk)
        self.komut_girdi.delete(0, "end")
        self.komut_girdi.insert(0, metin)
        self.komut_girdi.icursor("end")
        self.komut_girdi.focus_set()
        self.durumu_tazele()

    def komut_iptal(self) -> None:
        self.komut_girdi.pack_forget()
        self._duzenlenen_not = None     # Esc: yazilan not atilir
        self.mod = "normal"
        self.tuval.focus_set()
        self.durumu_tazele()

    def komut_onayla(self, olay=None) -> str:
        ham = self.komut_girdi.get()
        if self.mod == "not":
            n = self._duzenlenen_not          # komut_iptal bunu temizliyor
            self.komut_girdi.pack_forget()
            self.mod = "normal"
            self.tuval.focus_set()
            self._duzenlenen_not = n
            self.not_onayla(ham)
            return "break"
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
                self.tema_uygula(tema_kimligi(arg))
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
            self.yer_imi_koy(arg or None)
        elif ad == "blist":
            self.yer_imi_listesi()
        elif ad == "bdelete":
            if self.belge:
                for im in [im for im in self._yer_imleri() if im["ad"] == arg]:
                    self.yer_imi_sil(im)
        elif ad == "export":
            self.disa_aktar(arg)
        elif katla(ad) in ("redact", "karart", "schwarzen", "schwaerzen"):
            self.karart_ara(arg)
        elif ad == "tex" and arg:
            self.tex_ac(arg)
        elif ad == "info":
            self.bilgi()
        elif ad == "toc":
            self.icindekiler()
        elif ad == "rotate":
            self.dondur()
        elif ad == "rc":
            self.bildir(self.yapi.yol, "vurgu")
        elif ad == "help":
            self.bildir(self.m("yardim"), "vurgu")
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
            "asagi":        lambda: self.kaydir(self.ayar["kaydirma-adimi"] * self.sayi()),
            "yukari":       lambda: self.kaydir(-self.ayar["kaydirma-adimi"] * self.sayi()),
            "sola":         lambda: self.yatay_kaydir(-self.sayi()),
            "saga":         lambda: self.yatay_kaydir(self.sayi()),
            "yarim-asagi":  lambda: self.kaydir(self.gorunur_yukseklik() / 2),
            "yarim-yukari": lambda: self.kaydir(-self.gorunur_yukseklik() / 2),
            "sayfa-ileri":  lambda: self.kaydir(self.gorunur_yukseklik() * 0.92),
            "sayfa-geri":   lambda: self.kaydir(-self.gorunur_yukseklik() * 0.92),
            "sonraki-sayfa": lambda: self.sayfaya_git(self.aktif_sayfa + self.sayi(), zipla=False),
            "onceki-sayfa": lambda: self.sayfaya_git(self.aktif_sayfa - self.sayi(), zipla=False),
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
            "not-ekle": self.not_ekle,
            "geri-getir": self.geri_getir,
            "silme-kipi": self.silme_kipi_degistir,
            "vurgulari-aktar": self.vurgulari_aktar,
            "sayfa-duzeni": self.sayfa_duzeni,
            "birlestir":    self.birlestir,
            "karartma-kalemi": self.karartma_kalemi_degistir,
            "karartmayi-uygula": self.karartmayi_uygula,
            "ustveri-temizle": self.ustveri_temizle,
            "kopyala":      self.kopyala,
            "tex-modu":     self.tex_modu,
            "tex-derle":    self.tex_derle,
            "tex-kapat":    self.tex_kapat,
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
            "bolme-saga":   lambda: self.belgeyi_bolmeye(True),
            "bolme-sola":   lambda: self.belgeyi_bolmeye(False),
            "bolme-gec":    self.bolme_gec,
            "bolme-tek":    self.bolme_tek,
            "geri-acma-siniri": self.sinir_menusu,
            "yazici":       self.yazici_menusu,
            "tepsi":        self.tepsi_degistir,
            "belgeler":     self.belge_listesi,
            "tema":         self.tema_menusu,
            **{f"tema-{t}": (lambda t=t: self.tema_uygula(t)) for t in TEMALAR},
            "vurgu-renkleri": self.vurgu_renk_menusu,
            "yer-imi-koy":  self.yer_imi_koy,
            "yer-imleri":   self.yer_imi_listesi,
            "yazdir":       self.yazdir,
            "yazdir-sec":   self.yazdir_sec,
            "baglantilar":  self.baglantilari_goster,
            "isaret-koy":   lambda: self.bekle("isaret-koy"),
            "isarete-git":  lambda: self.bekle("isarete-git"),
        }

    def sayi(self) -> int:
        """Bekleyen sayi onekini tuketir (5j, 42G gibi); onek yoksa 1."""
        sayac, self.sayac = self.sayac, ""
        try:
            return max(1, int(sayac))
        except ValueError:          # bos, ya da int()'in okumadigi bir rakam (²)
            return 1

    def son_sayfa(self) -> None:
        if not self.belge:
            return
        if self.sayac:                      # 42G -> 42. sayfa
            self.sayfaya_git(self.sayi() - 1)
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
        adim = self.ayar["yakinlastirma-adimi"] ** (oran * self.sayi())
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
        self._tuvali_temizle()
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

    def _gece_renkleri(self) -> tuple[int, int] | None:
        """`gece-modu tema` icin (siyahin, beyazin) yeni rengi; `ters` ise None."""
        if str(self.ayar["gece-modu"]).strip().lower() in ("ters", "invert", "umkehren"):
            return None
        try:
            return int(self.ayar["cubuk-on"].lstrip("#"), 16), int(self.ayar["zemin"].lstrip("#"), 16)
        except (ValueError, AttributeError):
            return None

    def ters_renk(self) -> None:
        self.ters = not self.ters
        self.yenile()
        anahtar = "gece_modu_durum" if self._gece_renkleri() else "ters_renk_durum"
        self.bildir(self.m(anahtar, durum=self.m("acik" if self.ters else "kapali")), "vurgu")

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
        self._kalici_bildir(self.m("ust_bar_durum", durum=self.m("acik" if acik else "kapali")),
                            self.rc_tus_yaz({}, ayarlar={"baslik-cubugu": "true" if acik else "false"}))

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
            # before= kardes isteyor: tuval artik bolmenin cercevesinin icinde,
            # pencerede onun yerine tuval alani duruyor.
            self.ust_bar.pack(side="top", fill="x", before=self.tuval_alani)
        elif not gorunsun and self.ust_bar.winfo_ismapped():
            self.ust_bar.pack_forget()

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
            filetypes=[(self.m("ac_belgeler"), "*.pdf *.epub *.xps *.cbz *.mobi *.fb2 *.tex"),
                       ("PDF", "*.pdf"), ("TeX", "*.tex"), (self.m("ac_tumu"), "*.*")],
        )
        tex = [y for y in yollar if y.lower().endswith(".tex")]
        yollar = [y for y in yollar if not y.lower().endswith(".tex")]
        self._arkadakileri_ekle(list(yollar))
        if yollar:
            self.belgeyi_ac(yollar[-1])
        if tex:                                   # .tex listeye girmez, tex modunda acilir
            self.tex_ac(tex[-1])

    # -- tex modu (T) ------------------------------------------------------
    #
    # Tuval alaninin bir yaninda .tex kaynagi (tk.Text), kalaninda bolmeler.
    # Yazmayi `tex-gecikme` ms birakinca kaynak kaydedilir ve derlenir; Ctrl-S
    # hemen derler. latex `%LOCALAPPDATA%\rubric\tex\` altindaki kendi dizininde
    # calisir (aux / log kaynagin yanini kirletmesin); basariliysa PDF kaynagin
    # yanina `<ad>.pdf` olarak kopyalanir ve onu gosteren bolme kaldigi yerden
    # yeniden yuklenir. Hata varsa eski PDF durur, satir numarasi kizarir.
    #
    # Kopyalamadan once PDF kapatilir: MuPDF dosyayi acik tutuyor, ustune
    # yazilirken okumak da yazmak da bozulurdu.
    #
    # Editorde vim tuslari yok, duz yazi: tus_geldi odak editordeyken hicbir
    # tusu almaz. Esc PDF'e gecer, T geri getirir, Ctrl-W modu kapatir.

    def tex_modu(self) -> None:
        """T: kapaliysa ortada "yeni dosya / dosya ac" kartini acar (kullanici
        istegi, 2026-09-23: buyuk, ortada, Ctrl-K paleti olmadan; PDF'in
        yanindaki .tex'i kendiliginden aramasin), aciksa editore gecer."""
        if self.tex:
            self.tex_metin.focus_set()
            return
        if self.mod == "palet":
            self.paleti_kapat()
        if self.tex_karti is None:
            self._tex_kartini_kur()
        self._tex_karti_renkleri()
        self._tex_karti_secili = 0
        self._tex_kartini_ciz()
        self.tex_karti.place(relx=0.5, rely=0.45, anchor="center")
        self.tex_karti.lift()
        self.tex_karti.focus_set()

    # (tus, metin anahtari, aciklama anahtari, secim)
    _TEX_KARTI_SATIRLARI = (("n", "tex_yeni", "tex_yeni_aciklama", "yeni"),
                            ("o", "tex_dosya_ac", "tex_ac_aciklama", "ac"))

    def _tex_kartini_kur(self) -> None:
        """T'nin secim karti: paletten bagimsiz, ortada, iki buyuk satir."""
        k = self.tex_karti = tk.Frame(self, bd=0, highlightthickness=1, takefocus=True)
        self.tex_karti_baslik = tk.Label(k, anchor="w", bd=0, padx=22, pady=12)
        self.tex_karti_baslik.pack(side="top", fill="x")
        self.tex_karti_cizgi = tk.Frame(k, height=1, bd=0)
        self.tex_karti_cizgi.pack(side="top", fill="x")
        self.tex_karti_satirlar = []
        for i in range(len(self._TEX_KARTI_SATIRLARI)):
            e = tk.Label(k, anchor="w", bd=0, padx=22, pady=14, cursor="hand2")
            e.pack(side="top", fill="x")
            e.bind("<Enter>", lambda _e, i=i: self._tex_karti_git(i))
            e.bind("<Button-1>", lambda _e, i=i: self._tex_karti_sec(i))
            self.tex_karti_satirlar.append(e)
        self.tex_karti_alt_cizgi = tk.Frame(k, height=1, bd=0)
        self.tex_karti_alt_cizgi.pack(side="top", fill="x")
        self.tex_karti_ipucu = tk.Label(k, anchor="w", bd=0, padx=22, pady=6)
        self.tex_karti_ipucu.pack(side="top", fill="x")
        k.bind("<Key>", self._tex_karti_tus)
        # Baska yere tiklayinca kart kapanir. Satira tiklamak odagi almaz
        # (Label), yani o tik once kapatip sonra secmeyi bozmaz.
        k.bind("<FocusOut>", lambda _e: self._tex_kartini_kapat())

    def _tex_karti_renkleri(self) -> None:
        a = self.ayar
        buyuk = (a["yazitipi"], a["yazitipi-boy"] + 4)
        orta = (a["yazitipi"], a["yazitipi-boy"] + 2)
        yt = (a["yazitipi"], a["yazitipi-boy"])
        z = a["palet-zemin"]
        self.tex_karti.config(bg=z, highlightbackground=a["vurgu"], highlightcolor=a["vurgu"])
        self.tex_karti_baslik.config(bg=z, fg=a["vurgu"], font=buyuk, text="$ tex")
        for c in (self.tex_karti_cizgi, self.tex_karti_alt_cizgi):
            c.config(bg=a["palet-cerceve"])
        for e in self.tex_karti_satirlar:
            e.config(font=orta)
        self.tex_karti_ipucu.config(bg=a["cubuk-zemin"], fg=a["sonuk"], font=yt,
                                    text=self.m("tex_karti_ipucu"))

    def _tex_kartini_ciz(self) -> None:
        a = self.ayar
        adlar = [self.m(ad) for _, ad, _, _ in self._TEX_KARTI_SATIRLARI]
        en = max(len(ad) for ad in adlar) + 4
        for i, (e, (tus, _, aciklama, _)) in enumerate(zip(self.tex_karti_satirlar,
                                                          self._TEX_KARTI_SATIRLARI)):
            secili = i == self._tex_karti_secili
            e.config(text=f"{'>' if secili else ' '} [{tus}] {adlar[i].ljust(en)}"
                          f"{self.m(aciklama)}",
                     bg=a["panel-secili"] if secili else a["palet-zemin"],
                     fg=a["vurgu"] if secili else a["cubuk-on"])

    def _tex_karti_git(self, i: int) -> None:
        self._tex_karti_secili = i % len(self._TEX_KARTI_SATIRLARI)
        self._tex_kartini_ciz()

    def _tex_karti_tus(self, olay) -> str:
        ad = olay.keysym
        if ad in ("j", "Down", "Tab"):
            self._tex_karti_git(self._tex_karti_secili + 1)
        elif ad in ("k", "Up", "ISO_Left_Tab"):
            self._tex_karti_git(self._tex_karti_secili - 1)
        elif ad in ("Return", "KP_Enter", "space"):
            self._tex_karti_sec(self._tex_karti_secili)
        elif ad in ("Escape", "q"):
            self._tex_kartini_kapat()
        else:
            for i, (tus, _, _, _) in enumerate(self._TEX_KARTI_SATIRLARI):
                if ad == tus:
                    self._tex_karti_sec(i)
                    break
        return "break"

    def _tex_kartini_kapat(self) -> None:
        if self.tex_karti is not None and self.tex_karti.winfo_ismapped():
            self.tex_karti.place_forget()
            if self.focus_get() in (self.tex_karti, None):
                self.tuval.focus_set()

    def _tex_karti_sec(self, i: int) -> None:
        self._tex_kartini_kapat()
        self._tex_sec(self._TEX_KARTI_SATIRLARI[i][3])

    def _tex_sec(self, secim: str) -> None:
        """Secim menusunden: yeni dosya (nereye kaydedilecegi sorulur, sablonla
        yaratilir) ya da var olan bir .tex. Ikisinde de dosyanin yeri bastan
        belli: canli derleme hem .tex'i hem PDF'i hep diske yazar."""
        dizin = os.path.dirname(self.pdf_yolu) if self.pdf_yolu else os.path.expanduser("~")
        if secim == "yeni":
            yol = filedialog.asksaveasfilename(
                title=self.m("tex_yeni_baslik"), initialdir=dizin, initialfile="yeni.tex",
                defaultextension=".tex", filetypes=[("TeX", "*.tex")])
        else:
            yol = filedialog.askopenfilename(
                title=self.m("tex_sec"), initialdir=dizin,
                filetypes=[("TeX", "*.tex"), (self.m("ac_tumu"), "*.*")])
        if yol:
            self.tex_ac(yol)

    def tex_ac(self, yol: str) -> None:
        """`yol`daki .tex'i editore alir (yoksa sablonla yaratir), PDF'ini acar."""
        yol = os.path.abspath(os.path.expanduser(yol.strip().strip('"')))
        if not yol.lower().endswith(".tex"):
            yol += ".tex"
        if self.tex:
            if self._ayni_yol(self.tex["yol"], yol):
                self.tex_metin.focus_set()
                return
            self._tex_durdur()
        try:
            if os.path.exists(yol):
                with open(yol, "rb") as f:
                    ham = f.read()
            else:
                ham = TEX_SABLONU.encode("utf-8")
                with open(yol, "wb") as f:
                    f.write(ham)
        except OSError as e:
            self.bildir(self.m("tex_yazilamadi", ad=os.path.basename(yol), e=e), "hata")
            return
        # Kodlama korunur: utf-8 degilse ayni kodlamayla geri yazilir.
        kodlama = "utf-8-sig" if ham.startswith(b"\xef\xbb\xbf") else "utf-8"
        for k in (kodlama, "cp1254", "latin-1"):
            try:
                metin = ham.decode(k)
                kodlama = k
                break
            except UnicodeDecodeError:
                continue

        if self.tex_metin is None:
            self._tex_arayuzu_kur()
        self.tex = {"yol": yol, "kodlama": kodlama,
                    "satir_sonu": "\r\n" if b"\r\n" in ham else "\n",
                    "kirli": False, "isi": None, "boya_isi": None, "surec": None,
                    "bekliyor": False, "basla": 0.0, "durum": None, "hata_satiri": None,
                    "bolme": self.bolme}
        m = self.tex_metin
        m.delete("1.0", "end")
        m.insert("1.0", metin.replace("\r\n", "\n"))
        m.edit_reset()
        m.edit_modified(False)
        m.mark_set("insert", "1.0")
        m.see("insert")
        self._tex_renkleri()
        self._tex_boya()
        self._bolmeleri_yerlestir()
        self.yenile()

        hedef = self._tex_pdf_yolu()
        if os.path.exists(hedef) and not any(b.belge and self._ayni_yol(b.pdf_yolu, hedef)
                                             for b in self.bolmeler):
            self.belgeyi_ac(hedef)
        # PDF yoksa ya da kaynaktan eskiyse hemen derle
        if not os.path.exists(hedef) or os.path.getmtime(hedef) < os.path.getmtime(yol):
            self.tex_derle()
        self._tex_basligi()
        m.focus_set()
        self.bildir(self.m("tex_acildi", ad=os.path.basename(yol)), "vurgu")

    def _tex_arayuzu_kur(self) -> None:
        """Editorun parcalari: baslik satiri, satir numaralari, metin."""
        self.tex_cerceve = tk.Frame(self.tuval_alani, bd=0)
        self.tex_cerceve.pack_propagate(False)       # genislik ayardan, icerikten degil
        self.tex_cizgi = tk.Frame(self.tuval_alani, width=1, bd=0)   # tam 1 px ayirici
        self.tex_ust = tk.Label(self.tex_cerceve, anchor="w", bd=0, padx=8, pady=3)
        self.tex_ust.pack(side="top", fill="x")
        self.tex_ic = tk.Frame(self.tex_cerceve, bd=0)
        self.tex_ic.pack(side="top", fill="both", expand=True)
        self.tex_numara = tk.Canvas(self.tex_ic, bd=0, highlightthickness=0, takefocus=False)
        self.tex_numara.pack(side="left", fill="y")
        self.tex_metin = tk.Text(self.tex_ic, bd=0, highlightthickness=0, undo=True,
                                 maxundo=-1, wrap="word", padx=6, pady=4, width=1, height=1,
                                 insertwidth=2, exportselection=False,
                                 yscrollcommand=lambda *_: self._tex_numaralari_ciz())
        self.tex_metin.pack(side="left", fill="both", expand=True)
        m = self.tex_metin
        m.bind("<<Modified>>", self._tex_degisti)
        m.bind("<Control-s>", self.tex_derle)
        m.bind("<Control-S>", self.tex_derle)
        m.bind("<Control-w>", self.tex_kapat)
        m.bind("<Escape>", lambda e: (self.tuval.focus_set(), "break")[1])
        m.bind("<Tab>", lambda e: (m.insert("insert", "  "), "break")[1])
        m.bind("<Configure>", lambda e: self._tex_numaralari_ciz())
        self.tuval_alani.bind("<Configure>", self._tex_olcu_degisti)

    def _tex_genisligi(self) -> int:
        try:
            oran = max(15, min(85, int(self.ayar["tex-oran"])))
        except (TypeError, ValueError):
            oran = 50
        w = self.tuval_alani.winfo_width()
        if w <= 1:
            w = self.winfo_width()
        return max(120, w * oran // 100)

    def _tex_olcu_degisti(self, _olay=None) -> None:
        if self.tex and int(self.tex_cerceve.cget("width")) != self._tex_genisligi():
            self.tex_cerceve.config(width=self._tex_genisligi())

    def _tex_renkleri(self) -> None:
        a = self.ayar
        yt = (a["yazitipi"], a["yazitipi-boy"])
        olcu = tkfont.Font(self, font=yt)
        zemin = a["panel-zemin"]
        self.tex_cerceve.config(bg=zemin)
        self.tex_ic.config(bg=zemin)
        self.tex_cizgi.config(bg=a["palet-cerceve"])
        self.tex_ust.config(bg=a["cubuk-zemin"], font=yt)
        self.tex_numara.config(bg=zemin, width=olcu.measure("0000") + 10)
        self.tex_metin.config(bg=zemin, fg=a["cubuk-on"], insertbackground=a["vurgu"],
                              selectbackground=a["panel-secili"], selectforeground=a["vurgu"],
                              inactiveselectbackground=a["panel-secili"], font=yt,
                              tabs=(olcu.measure("    "),))
        m = self.tex_metin
        m.tag_config("tex_komut", foreground=a["vurgu"])
        m.tag_config("tex_mat", foreground=a["uyari"])
        m.tag_config("tex_parantez", foreground=a["sonuk"])
        m.tag_config("tex_yorum", foreground=a["sonuk"])
        m.tag_config("tex_hata", background=a["panel-secili"])
        self._tex_basligi()
        self._tex_numaralari_ciz()

    def _tex_basligi(self) -> None:
        t = self.tex
        if not t or self.tex_metin is None:
            return
        a = self.ayar
        durum, renk = "", a["cubuk-on"]
        if t["surec"] is not None:
            durum, renk = self.m("tex_derleniyor"), a["uyari"]
        elif t["durum"] and t["durum"][0] == "hata":
            satir = t["durum"][1]
            durum = self.m("tex_hatali", satir=satir) if satir else self.m("tex_hatali_satirsiz")
            renk = a["hata"]
        elif t["durum"] and t["durum"][0] == "tamam":
            durum = self.m("tex_tamam", sn=f"{t['durum'][1]:.1f}")
        if t["kirli"] and t["surec"] is None:
            durum = (self.m("tex_kirli") + " " + durum).strip()
        self.tex_ust.config(text=f"$ tex  {os.path.basename(t['yol'])}  {durum}", fg=renk)

    def _tex_numaralari_ciz(self) -> None:
        """Gorunen satirlarin numaralari; hatali satir `hata` renginde."""
        if self.tex_metin is None:
            return
        c, m, a = self.tex_numara, self.tex_metin, self.ayar
        c.delete("all")
        genislik = int(c.cget("width"))
        hata = self.tex["hata_satiri"] if self.tex else None
        yt = (a["yazitipi"], a["yazitipi-boy"])
        i = m.index("@0,0")
        while True:
            d = m.dlineinfo(i)
            if d is None:
                break
            no = int(i.split(".")[0])
            c.create_text(genislik - 6, d[1], anchor="ne", text=str(no), font=yt,
                          fill=a["hata"] if no == hata else a["sonuk"])
            sonraki = m.index(f"{i}+1line")
            if sonraki == i:
                break
            i = sonraki

    def _tex_degisti(self, _olay=None) -> None:
        m = self.tex_metin
        if not self.tex or not m.edit_modified():
            return
        m.edit_modified(False)
        t = self.tex
        t["kirli"] = True
        self._tex_basligi()
        if t["boya_isi"] is None:
            t["boya_isi"] = self.after(150, self._tex_boya)
        if t["isi"] is not None:
            self.after_cancel(t["isi"])
            t["isi"] = None
        try:
            gecikme = int(self.ayar["tex-gecikme"])
        except (TypeError, ValueError):
            gecikme = 800
        if gecikme > 0:
            t["isi"] = self.after(gecikme, self.tex_derle)

    def _tex_boya(self) -> None:
        """Komut, matematik, yorum ve parantezleri satir satir boyar."""
        if not self.tex:
            return
        self.tex["boya_isi"] = None
        m = self.tex_metin
        for etiket, _ in _TEX_DESENLER:
            m.tag_remove(etiket, "1.0", "end")
        for no, satir in enumerate(m.get("1.0", "end-1c").split("\n"), 1):
            if not satir:
                continue
            for etiket, desen in _TEX_DESENLER:
                for e in desen.finditer(satir):
                    m.tag_add(etiket, f"{no}.{e.start()}", f"{no}.{e.end()}")
        m.tag_raise("tex_yorum")

    def _tex_pdf_yolu(self) -> str:
        return os.path.splitext(self.tex["yol"])[0] + ".pdf"

    def _tex_dizini(self) -> str:
        """Kaynaga ozel derleme dizini; ayni adli iki .tex karismasin diye yolun ozeti."""
        yol = self.tex["yol"]
        ozet = hashlib.sha1(os.path.normcase(yol).encode("utf-8")).hexdigest()[:8]
        ad = os.path.splitext(os.path.basename(yol))[0]
        dizin = os.path.join(veri_dizini(), "tex", f"{ad}-{ozet}")
        os.makedirs(dizin, exist_ok=True)
        return dizin

    def _tex_kaydet(self) -> bool:
        t = self.tex
        metin = self.tex_metin.get("1.0", "end-1c")
        try:
            with open(t["yol"], "w", encoding=t["kodlama"], newline=t["satir_sonu"]) as f:
                f.write(metin)
        except (OSError, UnicodeEncodeError) as e:
            self.bildir(self.m("tex_yazilamadi", ad=os.path.basename(t["yol"]), e=e), "hata")
            return False
        t["kirli"] = False
        self.tex_metin.edit_modified(False)   # kuyruktaki <<Modified>> yeniden kirletmesin
        return True

    def tex_derle(self, _olay=None) -> str:
        """Kaydeder ve latex'i baslatir. Derleme surerken gelen istek sona
        eklenir: biter bitmez bir kez daha derlenir."""
        t = self.tex
        if not t:
            self.bildir(self.m("tex_kapali"), "uyari")
            return "break"
        if t["isi"] is not None:
            self.after_cancel(t["isi"])
            t["isi"] = None
        if t["surec"] is not None:
            t["bekliyor"] = True
            return "break"
        # <<Modified>> kuyrukta olabilir: bayraga da bak
        if (t["kirli"] or self.tex_metin.edit_modified()) and not self._tex_kaydet():
            return "break"
        motor = str(self.ayar["tex-motoru"]).strip() or "pdflatex"
        exe = shutil.which(motor)
        if not exe:
            self.bildir(self.m("tex_motor_yok", motor=motor), "hata")
            return "break"
        komut = [exe, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
                 f"-output-directory={self._tex_dizini()}", os.path.basename(t["yol"])]
        try:
            t["surec"] = subprocess.Popen(
                komut, cwd=os.path.dirname(t["yol"]), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            self.bildir(self.m("tex_hata_satirsiz", ileti=e), "hata")
            return "break"
        t["basla"] = time.monotonic()
        self._tex_basligi()
        self.after(120, self._tex_bekle)
        return "break"

    def _tex_bekle(self) -> None:
        t = self.tex
        if not t or t["surec"] is None:
            return
        kod = t["surec"].poll()
        sure = time.monotonic() - t["basla"]
        if kod is None:
            if sure > TEX_ZAMAN_ASIMI:
                t["surec"].kill()
                t["surec"] = None
                t["durum"] = ("hata", None)
                self._tex_basligi()
                self.bildir(self.m("tex_zaman_asimi", sn=TEX_ZAMAN_ASIMI), "hata")
            else:
                self.after(120, self._tex_bekle)
            return
        t["surec"] = None
        ad = os.path.splitext(os.path.basename(t["yol"]))[0]
        uretilen = os.path.join(self._tex_dizini(), ad + ".pdf")
        if kod == 0 and os.path.exists(uretilen):
            self._tex_hata_isaretle(None)
            if self._tex_pdfi_guncelle(uretilen):
                t["durum"] = ("tamam", sure)
                self.bildir(self.m("tex_derlendi", sn=f"{sure:.1f}",
                                   ad=os.path.basename(self._tex_pdf_yolu())), "vurgu")
        else:
            dosya, satir, ileti = self._tex_hatasi(os.path.join(self._tex_dizini(), ad + ".log"))
            ana = dosya is None or os.path.basename(dosya) == os.path.basename(t["yol"])
            self._tex_hata_isaretle(satir if ana else None)
            t["durum"] = ("hata", satir if ana else None)
            if satir:
                self.bildir(self.m("tex_hata", dosya=os.path.basename(dosya or t["yol"]),
                                   satir=satir, ileti=ileti), "hata")
            else:
                self.bildir(self.m("tex_hata_satirsiz", ileti=ileti or f"exit {kod}"), "hata")
        self._tex_basligi()
        if t["bekliyor"]:
            t["bekliyor"] = False
            self.tex_derle()

    @staticmethod
    def _tex_hatasi(log_yolu: str) -> tuple[str | None, int | None, str]:
        """latex gunlugunden ilk hata: (dosya, satir, ileti). -file-line-error
        satiri yoksa "! ..." satiri ve ardindaki "l.<n>" okunur."""
        try:
            with open(log_yolu, encoding="latin-1") as f:
                log = f.read()
        except OSError:
            return None, None, ""
        e = _TEX_HATA.search(log)
        if e:
            return e.group(1), int(e.group(2)), e.group(3).strip()
        e = re.search(r"^! (.*)$", log, re.M)
        if e:
            satir = re.search(r"^l\.(\d+)", log[e.end():], re.M)
            return None, int(satir.group(1)) if satir else None, e.group(1).strip()
        return None, None, ""

    def _tex_hata_isaretle(self, satir: int | None) -> None:
        m = self.tex_metin
        m.tag_remove("tex_hata", "1.0", "end")
        self.tex["hata_satiri"] = satir
        if satir:
            m.tag_add("tex_hata", f"{satir}.0", f"{satir}.0 lineend+1c")
        self._tex_numaralari_ciz()

    def _tex_pdfi_guncelle(self, uretilen: str) -> bool:
        """Derlenen PDF'i kaynagin yanina koyar; onu gosteren bolmeler kaldigi
        yerden (ofset, zoom, sigdirma) yeniden yuklenir. Ilk derlemede PDF
        hicbir bolmede acik degilse tex'in acildigi bolmede acilir."""
        t = self.tex
        hedef = self._tex_pdf_yolu()
        acik = []
        for b in self.bolmeler:
            with self._bolmede(b):
                if self.belge is not None and self._ayni_yol(self.pdf_yolu, hedef):
                    acik.append((b, self.ofset(), self.zoom, self.sigdir))
                    self.konumu_kaydet(diske=False)
                    self.belge.close()
                    self.belge = None
        hata = None
        try:
            shutil.copyfile(uretilen, hedef)
        except OSError as e:
            hata = e
        for b, yer, zoom, sigdir in acik:
            with self._bolmede(b):
                self.belgeyi_ac(hedef)
                if self.belge is not None:
                    self.zoom, self.sigdir = zoom, sigdir
                    self.duzeni_hesapla()
                    self.ofset_ata(yer, ciz=True)
        if not acik and not hata and not t.get("gosterildi"):
            bolme = t["bolme"] if t["bolme"] in self.bolmeler else self.bolme
            with self._bolmede(bolme):
                self.belgeyi_ac(hedef)
        t["gosterildi"] = True
        if hata:
            self.bildir(self.m("tex_pdf_kilitli", ad=os.path.basename(hedef), e=hata), "hata")
            t["durum"] = ("hata", None)
            return False
        return True

    def _tex_durdur(self) -> None:
        """Bekleyen isleri iptal eder, suren latex'i oldurur, yazilani kaydeder."""
        t = self.tex
        for isim in ("isi", "boya_isi"):
            if t[isim] is not None:
                self.after_cancel(t[isim])
                t[isim] = None
        if t["surec"] is not None:
            try:
                t["surec"].kill()
            except OSError:
                pass
            t["surec"] = None
        if t["kirli"] or self.tex_metin.edit_modified():
            self._tex_kaydet()

    def tex_kapat(self, _olay=None) -> str:
        if not self.tex:
            self.bildir(self.m("tex_kapali"), "uyari")
            return "break"
        self._tex_durdur()
        ad = os.path.basename(self.tex["yol"])
        self.tex = None
        self._bolmeleri_yerlestir()
        self.yenile()
        self.tuval.focus_set()
        self.bildir(self.m("tex_kapandi", ad=ad), "vurgu")
        return "break"

    # -- yer imleri (M koy, b liste) ---------------------------------------
    #
    # durum.json'da dosya kaydinin `yer-imleri` listesi: {ad, sayfa, oran, zaman}.
    # Konum konum_imi() ikilisi, yani zoom ve pencere boyundan bagimsiz. Eski
    # surum {ad: piksel ofseti} yaziyordu; o deger zoom'a bagli oldugu icin
    # kullanilamaz, ilk yazista liste bastan kurulur.

    def _yer_imleri(self) -> list[dict]:
        kayit = self.kalici.dosya(self.pdf_yolu)
        imler = kayit.get("yer-imleri")
        if not isinstance(imler, list):
            imler = kayit["yer-imleri"] = []
        toplam = self.belge.page_count if self.belge else 0
        imler[:] = [im for im in imler if isinstance(im, dict) and im.get("ad")
                    and 0 <= int(im.get("sayfa", -1)) < toplam]
        return imler

    def _bolum_adi(self, sayfa: int) -> str:
        """Sayfanin icinde bulundugu en son baslik (icindekilerden); yoksa bos."""
        ad, en_iyi = "", -1
        try:
            toc = self.belge.get_toc()
        except Exception:
            toc = []
        for _, baslik, s in toc:
            if en_iyi <= s - 1 <= sayfa:           # esitlikte sonraki: en alt baslik
                ad, en_iyi = baslik, s - 1
        ad = " ".join(ad.split())
        return ad if len(ad) <= 60 else ad[:57] + "..."

    def yer_imi_koy(self, ad: str | None = None) -> None:
        """Bulunulan yere yer imi. Ad verilmezse bolumun basligi. Ayni sayfada
        zaten adsiz konmus bir yer imi varsa yeni satir acmaz, yerini gunceller;
        `:bmark <ad>` ayni adla yeniden verilirse o yer imini buraya tasir."""
        if not self.belge or not self.pdf_yolu:
            return
        # konum_imi() degil: J/42G sayfanin ustundeki bosluga iner, orasi bir
        # onceki sayfaya sayilir ve listede yanlis sayfa yazardi. Yer imi ekranda
        # bakilan sayfaya (aktif) baglanir; oran eksi de olabilir, geri donus aynidir.
        sayfa = self.aktif_sayfa
        yer = self.sayfa_yeri(sayfa)
        oran = (self.ofset() - yer["y"]) / max(1, yer["h"]) if yer else 0.0
        imler = self._yer_imleri()
        if ad:
            eski = next((im for im in imler if im["ad"] == ad), None)
        else:
            eski = next((im for im in imler if im["sayfa"] == sayfa), None)
            # elle verilmis adi (:bmark) koru; yoksa bolum basligi
            ad = eski["ad"] if eski else (self._bolum_adi(sayfa)
                                          or self.m("satir_sayfa", s=sayfa + 1))
        if eski is not None:
            imler.remove(eski)
        imler.append({"ad": ad, "sayfa": sayfa, "oran": round(oran, 4),
                      "zaman": time.strftime("%Y-%m-%d %H:%M")})
        self.kalici.yaz()
        if eski is not None and eski["sayfa"] == sayfa:
            self.bildir(self.m("yer_imi_var", ad=eski["ad"]), "vurgu")
        else:
            self.bildir(self.m("yer_imi", ad=ad, s=sayfa + 1), "vurgu")

    def yer_imi_listesi(self) -> None:
        """Kendi paneli (Tab'daki icindekilerden ayri): Enter git, x sil, a ekle."""
        if not self.belge or self._panel_kapandi("yer-imleri"):
            return
        imler = sorted(self._yer_imleri(), key=lambda im: (im["sayfa"], im["oran"]))
        if not imler:
            tus = (self.komut_tuslari().get("yer-imi-koy") or [f":{self.ad('yer-imi-koy')}"])[0]
            self.bildir(self.m("yer_imi_yok", tus=tus), "uyari")
            return
        self.panel_konumlari = imler
        secim = 0
        for i, im in enumerate(imler):
            if im["sayfa"] <= self.aktif_sayfa:
                secim = i
        self._paneli_ac("yer-imleri", [f"  [{im['sayfa'] + 1:>4}]  {im['ad']}" for im in imler],
                        secim)

    def yer_imi_sil(self, im: dict) -> None:
        imler = self._yer_imleri()
        if im in imler:
            imler.remove(im)
            self.kalici.yaz()
            self.bildir(self.m("silindi", ad=im["ad"]), "vurgu")

    def listeden_yer_imi_sil(self) -> None:
        secili = self.liste.curselection()
        if not secili:
            return
        i = secili[0]
        self.yer_imi_sil(self.panel_konumlari.pop(i))
        self.liste.delete(i)
        if not self.panel_konumlari:
            self.paneli_kapat()
        else:
            self._panel_satiri_sec(i)

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

    # -- yazdirma (<C-p>) --------------------------------------------------
    #
    # <C-p> Windows'un yazdirma penceresini acar (yazici, sayfa araligi,
    # kopya); `yazdir-sec` (P) ayar ne derse desin hep onu acar. Pencerede
    # varsayilan yazici secili gelir - Windows'ta cogu kez "Microsoft Print
    # to PDF", orada bir kez gercek yazici secilir. `set yazdirma-penceresi
    # false` <C-p>'yi pencere acmadan `yazdirma-yazicisi`na (bos ise
    # varsayilana) basan hale cevirir; tanimli yazici yoksa yine pencere acilir.
    #
    # Kural (bkz. DURUM "Pencere hatalari"): Tk geri cagrisinin icinden modal
    # Win32 penceresi acilmaz; onun ic mesaj dongusu tkinter'i GIL'siz
    # yakalayip sureci dusuruyordu. Bu yuzden pencere ve GDI isi ayri bir is
    # parcaciginda (_yazdirma_isi), MuPDF ise hep ana is parcaciginda: sayfalar
    # burada tek tek islenip kuyruga verilir (PyMuPDF is parcacigi guvenli
    # degil). Yazdirilan, ekranda gorulen: vurgular dahil, gece modu ve arama
    # isaretleri haric. Suren is varken <C-p> yeniden basilirsa iptal eder.

    def yazdir_sec(self) -> None:
        """P: Windows'un yazdirma penceresini acar (yazici, sayfa araligi, kopya)."""
        self.yazdir(pencere=True)

    def yazdir(self, yazici: str | None = None, cikti: str | None = None,
               pencere: bool | None = None) -> None:
        """`yazici` verilirse pencere acilmaz, butun sayfalar o yaziciya gider;
        `cikti` dosya yolu (Microsoft Print to PDF). Ikisi testler icin.
        `pencere` True ise ayar ne derse desin yazdirma penceresi acilir."""
        if self._baski is not None:
            self._baski["durdur"].set()
            self.bildir(self.m("yazdirma_iptal_ediliyor"), "uyari")
            return
        if not self.belge or not self.pdf_yolu:
            return
        if pencere is None:
            pencere = bool(self.ayar["yazdirma-penceresi"])
        if yazici is None and not pencere:
            yazici = str(self.ayar["yazdirma-yazicisi"]).strip() or _varsayilan_yazici()
            if not yazici:              # tanimli yazici yok: secmekten baska yol kalmaz
                self.bildir(self.m("varsayilan_yazici_yok"), "uyari")
        self.update_idletasks()
        b = {"cevap": queue.Queue(), "kuyruk": queue.Queue(maxsize=2),
             "durdur": threading.Event(), "yol": self.pdf_yolu,
             "vurgular": [dict(v) for v in self.vurgular] if self.belge.is_pdf else [],
             "belge": None, "sayfalar": [], "sira": 0, "yazici": "", "olcu": None,
             "kilitli": yazici is None}
        if b["kilitli"]:
            # Pencere acikken rubric tiklanmasin/tus almasin (modal gibi). Sahip
            # verilemedigi icin (bkz. _ortala_kancasi) kilidi Tk'nin kendisi vurur;
            # is parcacigindan ilk haber gelince (secim / iptal / hata) acilir.
            self.attributes("-disabled", True)
        b["is"] = threading.Thread(
            target=_yazdirma_isi, daemon=True,
            args=(int(self.wm_frame(), 16), self.belge.page_count, self.aktif_sayfa + 1,
                  os.path.basename(self.pdf_yolu), b["cevap"], b["kuyruk"], b["durdur"],
                  yazici, cikti))
        self._baski = b
        b["is"].start()
        self.after(50, self._baskiyi_yurut)

    def _baski_ilerlemesi(self, i: int) -> None:
        b = self._baski
        tus = (self.komut_tuslari().get("yazdir") or [f":{self.ad('yazdir')}"])[0]
        self.bildir(self.m("yazdiriliyor", i=i, n=len(b["sayfalar"]), yazici=b["yazici"],
                           tus=tus), "uyari")

    def _baskiyi_yurut(self) -> None:
        """Is parcaciginin haberlerini okur, siradaki sayfayi isleyip verir."""
        b = self._baski
        if b is None:
            return
        try:
            while True:
                olay = b["cevap"].get_nowait()
                self._baski_kilidini_ac(b)
                if olay[0] == "secim":
                    ilk, son, b["yazici"], *b["olcu"] = olay[1:]
                    b["sayfalar"] = list(range(max(1, ilk) - 1, min(son, self.belge.page_count
                                                                    if self.belge else son)))
                    b["belge"] = self._baski_belgesi(b)
                    self._baski_ilerlemesi(0)
                elif olay[0] == "sayfa":
                    self._baski_ilerlemesi(olay[1])
                else:                                   # bitti / iptal / hata
                    self._baskiyi_bitir(olay)
                    return
        except queue.Empty:
            pass
        except Exception as e:                          # kopya acilamadi vb.
            b["durdur"].set()
            self._baskiyi_bitir(("hata", str(e)))
            return

        kuyruk = b["kuyruk"]
        if b["belge"] is not None and not b["durdur"].is_set() and not kuyruk.full() \
                and b["sira"] <= len(b["sayfalar"]):
            if b["sira"] == len(b["sayfalar"]):
                kuyruk.put(None)                        # bitti isareti
            else:
                try:
                    kuyruk.put(self._baski_sayfasi(b, b["sayfalar"][b["sira"]]))
                except Exception as e:
                    b["durdur"].set()
                    self._baskiyi_bitir(("hata", str(e)))
                    return
            b["sira"] += 1
        self.after(15 if b["belge"] is not None else 100, self._baskiyi_yurut)

    def _baski_belgesi(self, b: dict) -> pymupdf.Document:
        """Yazdirma kendi kopyasindan yapilir: kullanici bu arada belge
        degistirse, kapatsa da is surer. Vurgular kopyaya yeniden islenir."""
        kopya = pymupdf.open(b["yol"])
        if kopya.is_pdf:
            sayfalar = set(b["sayfalar"])
            for v in b["vurgular"]:
                if int(v["sayfa"]) in sayfalar:
                    self._not_yaz(kopya, v)
        return kopya

    def _baski_sayfasi(self, b: dict, no: int) -> tuple:
        """Sayfayi yazicinin yazilabilir alanina oranini bozmadan sigdirir
        (kucultur, buyutmez) ve ortalar. Cozunurluk en cok 300 dpi."""
        en, boy, dpx, dpy = b["olcu"]
        r = b["belge"][no].rect
        k = min(1.0, en / (r.width / 72 * dpx), boy / (r.height / 72 * dpy))
        z = min(dpx, 300) / 72 * k
        pix = b["belge"][no].get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False,
                                        colorspace=pymupdf.csRGB)
        dw, dh = round(r.width / 72 * dpx * k), round(r.height / 72 * dpy * k)
        return (pix.width, pix.height, pix.samples, (en - dw) // 2, (boy - dh) // 2, dw, dh)

    def _baski_kilidini_ac(self, b: dict) -> None:
        if b.get("kilitli"):
            b["kilitli"] = False
            self.attributes("-disabled", False)
            self.focus_force()                  # pencere kapaninca odak rubric'e donsun
            self.tuval.focus_set()

    def _baskiyi_bitir(self, olay: tuple) -> None:
        b, self._baski = self._baski, None
        if b:
            self._baski_kilidini_ac(b)
        if b and b["belge"] is not None:
            b["belge"].close()
        if olay[0] == "bitti":
            self.bildir(self.m("yazdirildi", sayfalar=self.m("sayfa_n", n=olay[1]),
                               yazici=olay[2]), "vurgu")
        elif olay[0] == "iptal":
            self.bildir(self.m("yazdirma_iptal"), "uyari")
        else:
            self.bildir(self.m("yazdirilamadi", e=olay[1]), "hata")

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
        if self.tex_metin is not None and self.focus_get() in (self.tex_metin, self.tex_karti):
            return None                           # tex editoru / karti kendi tuslarini alir
        ad = self.tus_adini_coz(olay)
        if not ad:
            return None
        self.gecici_ileti = ""

        # sayfa duzeni butun tuslari kendisi alir: altta kalan belgeye gitmesin
        if self.mod == "sayfa-duzeni":
            self.duzen_tus(ad)
            return "break"

        # renk bekleyen secim: Enter varsayilan renk, renk tusu o renk, Esc birakir.
        # Renk tuslari yalnizca burada gecerli; baska tuslar (j, k...) her zamanki isi yapar.
        if self._bekleyen_vurgu is not None and self.bekleyen is None and not self.sayac:
            renk = self.vurgu_varsayilani() if ad == "<Return>" \
                else self.renk_tuslari().get(ad)
            if renk:
                self.bekleyeni_vurgula(renk)
                return "break"
            if ad == "<Esc>":
                self._secimi_birak()
                self.bildir(self.m("secim_birakildi"), "uyari")
                return "break"

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

        # karartma kalemi acikken Enter karartilmis kopyayi yazar
        if ad == "<Return>" and self.karartma_acik and not self.sayac:
            self.karartmayi_uygula()
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
        # Olcuden once: pencereyi tasimak boyu degistirmez, asagidaki erken
        # donus yuzunden yeni x/y hic kaydedilmezdi.
        self._konumu_hatirla()
        olcu = (self.winfo_width(), self.winfo_height())
        if self._son_olcu == olcu:
            return
        self._son_olcu = olcu
        if self._boyut_isi is not None:
            self.after_cancel(self._boyut_isi)
        self._boyut_isi = self.after(120, self.yenile)

    def yenile(self) -> None:
        """Duzeni bastan kurar; zoom/donme/sutun/pencere degisince cagrilir.
        Bolunmusse ikisini de: pencere buyudugunde ikisinin de genisligi degisir."""
        if self.mod == "palet":         # palet de pencereyle birlikte genisler
            self.update_idletasks()
            self._palet_genisligini_olc()
            self._paleti_yeniden_doldur()
        for b in self.bolmeler:
            with self._bolmede(b):
                self._bolmeyi_yenile()

    def _bolmeyi_yenile(self) -> None:
        if not self.belge:
            return
        if self._zoom_isi is not None:          # bekleyen tekerlek adimi kaybolmasin
            hedef = self._hedef_zoom
            self._bekleyen_zoomu_birak()
            if hedef:
                self.zoom = hedef
        im = self.konum_imi()
        self._tuvali_temizle()
        self.duzeni_hesapla()
        self.konum_imine_git(im, ciz=False)
        self.ciz()

    def ayarlar_degisti(self, gorunumu_koru: bool = False) -> None:
        """:set ya da tema sonrasi. `gorunumu_koru`: o an acilmis gece modu ve
        cift sayfa rubricrc'deki ters-renk / sutunlar'a donmesin."""
        self.ayar["yazitipi"] = self.yazitipi_sec(self.ayar["yazitipi"])
        self.metinleri_tazele()
        self._renkleri_uygula()
        self._ust_bari_yerlestir()
        self._ust_adi_sigdir()
        self.cerceveyi_uygula()
        for b in self.bolmeler:
            with self._bolmede(b):
                if not gorunumu_koru:
                    self.sutunlar = max(1, int(self.ayar["sutunlar"]))
                self._vurgulari_yeniden_isle()
                self.onbellek.clear()
        if not gorunumu_koru:
            self.ters = bool(self.ayar["ters-renk"])
        self.yenile()

    def _paleti_yeniden_doldur(self) -> None:
        """Palet listesini bastan kurar; secili komut secili kalir."""
        secili = self.palet_secili()
        self.palet_doldur()
        if secili:
            self._palet_komuta_git(secili)

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
               "belgeler": self.m("mod_belgeler"),
               "yer-imleri": self.m("mod_yer_imleri"),
               "sayfa-duzeni": self.m("mod_sayfa_duzeni")}.get(self.mod, "")
        if self.mod == "normal":
            mod = " ".join(self.m(a) for a, acik in (("mod_kalem", self.kalem),
                                                     ("mod_karartma", self.karartma_acik),
                                                     ("mod_baglantilar", self.baglantilar_acik))
                           if acik)
        if self.bekleyen:
            mod = self.m(f"bekle_{self.bekleyen}") if self.bekleyen != "g" else "[g]"
        sira = self._sira() if len(self.belgeler) > 1 else -1
        # Bolunmusse hangi bolmeye bakildigi da {belgeler} icinde: " [sag 2/3]".
        # Ayri yer tutucu isteyen icin {bolme} de var.
        yan = self._yan_adi(self.bolme) if self.bolundu() else ""
        liste = f"{sira + 1}/{len(self.belgeler)}" if sira >= 0 else ""
        return {
            "mod": mod,
            "dosya": os.path.basename(self.pdf_yolu) if self.pdf_yolu else "-",
            "ad": os.path.basename(self.pdf_yolu) if self.pdf_yolu else self.m("belge_yok"),
            "yol": self.pdf_yolu or "-",
            "bolme": f" [{yan}]" if yan else "",
            "belgeler": f" [{' '.join(x for x in (yan, liste) if x)}]" if (yan or liste) else "",
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
        """Durum cubugu ve pencere basligi. Her cizimde (her kaydirma adiminda)
        cagrilir; degismeyen parca yeniden yazilmaz. Basligin her yazilisi
        Win32'de WM_SETTEXT (bkz. _win32), tek basina ~0.7 ms tutuyordu."""
        d = self.durum_degerleri()
        if self.gecici_ileti:
            metin, renk = self.gecici_ileti, self._ileti_rengi
        else:
            try:
                metin = self.ayar["durum-bicimi"].format_map(_Esnek(d))
            except Exception:
                metin = f"{d['ad']}  {d['sayfa']}/{d['toplam']}"
            renk = self.ayar["cubuk-on"]
        sag = self.sayac or ""
        if self.belge:
            sag = f"{sag}  {d['sayfa']}/{d['toplam']}".strip()
        if (metin, renk, sag) != self._durum_yazili:
            self._durum_yazili = (metin, renk, sag)
            self.durum.config(text=metin, fg=renk)
            self.sag_durum.config(text=sag)

        try:
            baslik = self.ayar["baslik-bicimi"].format_map(_Esnek(d))
        except Exception:
            baslik = "rubric"
        if baslik != self._baslik:
            self._baslik = baslik
            self.title(baslik)
        if d["ad"] != self._ust_ad_ham:          # her kaydirmada olcmesin
            self._ust_ad_ham = d["ad"]
            self._ust_adi_sigdir()

    # -- cikis -------------------------------------------------------------

    def cik(self) -> None:
        if self._tepsi and not self._tamamen_cik:
            self._tepsiye_in()                  # tepsi modu: kapanmaz, gizlenir
            return
        self._tepsi_kaldir()
        for b in self.bolmeler:                 # her bolmenin bekleyen isleri
            with self._bolmede(b):
                self._bekleyen_zoomu_birak()
                for isim in ("_komsu_isi", "_capa_isi"):
                    if getattr(self, isim) is not None:
                        self.after_cancel(getattr(self, isim))
                        setattr(self, isim, None)
        if self._boyut_isi is not None:         # yoksa yok edilmis pencerede yenile() calisir
            self.after_cancel(self._boyut_isi)
        if self._ipc_isi is not None:           # tek-pencere yoklamasi da dursun
            self.after_cancel(self._ipc_isi)
            self._ipc_isi = None
        if self.tex:                            # tex: yazilan kaydedilsin, latex dursun
            self._tex_durdur()
        if self._baski is not None:             # suren yazdirma: is parcacigi belgeyi iptal etsin
            self._baski["durdur"].set()
            if self._baski["belge"] is not None:
                self._baski["belge"].close()
            self._baski = None
        for b in self.bolmeler:                 # her bolmenin kaldigi yer yazilsin
            with self._bolmede(b):
                self.konumu_kaydet()
        self.oturumu_kaydet()                   # acilista ayni bolmeler geri gelsin
        for b in self.bolmeler:
            try:
                if b.belge:
                    b.belge.close()
            except Exception:
                pass
        self.destroy()


def _bolme_ozelligi(ad: str) -> property:
    """`self.<ad>` -> `self.bolmeler[self.etkin].<ad>`.

    Dogrudan ozellik; `__getattr__`/`__setattr__` degil: butun oznitelik
    erisimini yavaslatmasin ve hangi adin bolmeye ait oldugu tek listede
    (BOLME_ALANLARI) acikca dursun.
    """
    return property(lambda s: getattr(s.bolmeler[s.etkin], ad),
                    lambda s, d: setattr(s.bolmeler[s.etkin], ad, d))


for _ad in BOLME_ALANLARI:
    setattr(Rubric, _ad, _bolme_ozelligi(_ad))
del _ad


class _Esnek(dict):
    """Bicim dizesinde bilinmeyen yer tutucu programi dusurmesin."""

    def __missing__(self, anahtar):
        return "{" + anahtar + "}"


def _pencere_dikdortgeni(pencere) -> tuple[int, int, int, int] | None:
    """Pencerenin gercek Win32 cercevesi: (en, boy, x, y). Olculemezse None.

    Neden Tk'nin geometry()'si degil: cerceveyi_uygula'nin WM_NCCALCSIZE
    kancasi istemci alanini baslik payina dogru buyutuyor, Tk ise eski
    payi hesaba katmaya devam ediyor. geometry() ile okuyup geometry() ile
    yazmak bu yuzden tam donus yapmiyor - pencere her acilista 2x34 px
    buyuyor. GetWindowRect / MoveWindow ikilisi ayni uzayda calisir."""
    if sys.platform != "win32":
        return None
    try:
        dik = wt.RECT()
        hwnd = wt.HWND(int(pencere.wm_frame(), 16))
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(dik)):
            return None
    except Exception:
        return None
    return dik.right - dik.left, dik.bottom - dik.top, dik.left, dik.top


def _pencereyi_tasi(pencere, en: int, boy: int, x: int, y: int) -> bool:
    """_pencere_dikdortgeni'nin tersi; basarisizsa False (cagiran Tk'ye duser)."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = wt.HWND(int(pencere.wm_frame(), 16))
        return bool(ctypes.windll.user32.MoveWindow(hwnd, x, y, en, boy, True))
    except Exception:
        return False


def _geometriyi_coz(g: str) -> tuple[int, int, int, int] | None:
    """Tk'nin "1000x760+180+90" dizesi -> (en, boy, x, y). Ekran solda ya da
    yukarida kalan monitorde negatif koordinat verir, isaret de okunur."""
    # Tk eksi koordinati "+-90" diye yazar, "-90" da olabilir: bastaki arti
    # istege bagli, isaret sayinin kendisinde.
    m = re.match(r"^(\d+)x(\d+)\+?(-?\d+)\+?(-?\d+)$", g.strip())
    if not m:
        return None
    return int(m[1]), int(m[2]), int(m[3]), int(m[4])


def _ekran_alani(pencere) -> tuple[int, int, int, int]:
    """Pencerenin konabilecegi alan: (x, y, genislik, yukseklik).

    Windows'ta butun monitorlerin kapsadigi "sanal ekran" olculur; Tk'nin
    winfo_screenwidth'i yalnizca birincil monitoru bilir, onunla hesaplarsak
    ikinci ekranda birakilmis pencere her acilista birinciye geri cekilir.
    Sanal ekran sol ust kosesi negatif olabilir (monitor solda duruyorsa),
    o yuzden genislik degil dort deger birden donuyor."""
    if sys.platform == "win32":
        try:
            u32 = ctypes.windll.user32
            olc = u32.GetSystemMetrics
            x, y, en, boy = olc(76), olc(77), olc(78), olc(79)   # SM_*VIRTUALSCREEN
            if en > 0 and boy > 0:
                return x, y, en, boy
        except Exception:
            pass                        # olcemedik: asagidaki Tk hesabina dus
    return 0, 0, pencere.winfo_screenwidth(), pencere.winfo_screenheight()


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


# ---------------------------------------------------------------------------
# Yazdirma: Windows yazdirma penceresi + GDI. Yalnizca _yazdirma_isi'nin is
# parcaciginda calisir (bkz. Rubric.yazdir); MuPDF'e hic dokunmaz.
# ---------------------------------------------------------------------------

_PD_PAGENUMS = 0x2
_PD_NOSELECTION = 0x4
_PD_RETURNDC = 0x100
_PD_ENABLEPRINTHOOK = 0x1000
_PD_USEDEVMODECOPIESANDCOLLATE = 0x40000
_PD_HIDEPRINTTOFILE = 0x100000


class _PRINTDLGW(ctypes.Structure):
    # 64 bit'te varsayilan hizalama (commdlg.h yalnizca 32 bit'te pack(1))
    _fields_ = [("lStructSize", wt.DWORD), ("hwndOwner", wt.HWND),
                ("hDevMode", wt.HGLOBAL), ("hDevNames", wt.HGLOBAL), ("hDC", wt.HDC),
                ("Flags", wt.DWORD), ("nFromPage", wt.WORD), ("nToPage", wt.WORD),
                ("nMinPage", wt.WORD), ("nMaxPage", wt.WORD), ("nCopies", wt.WORD),
                ("hInstance", wt.HINSTANCE), ("lCustData", wt.LPARAM),
                ("lpfnPrintHook", ctypes.c_void_p), ("lpfnSetupHook", ctypes.c_void_p),
                ("lpPrintTemplateName", wt.LPCWSTR), ("lpSetupTemplateName", wt.LPCWSTR),
                ("hPrintTemplate", wt.HGLOBAL), ("hSetupTemplate", wt.HGLOBAL)]


class _DOCINFOW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", wt.LPCWSTR),
                ("lpszOutput", wt.LPCWSTR), ("lpszDatatype", wt.LPCWSTR), ("fwType", wt.DWORD)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def _gdi():
    """gdi32/comdlg32/kernel32 imzalari; 64 bit tutamaclar int'e kirpilmasin."""
    if getattr(_gdi, "hazir", None):
        return _gdi.hazir
    g, cd, k32 = ctypes.WinDLL("gdi32"), ctypes.WinDLL("comdlg32"), ctypes.WinDLL("kernel32")
    cd.PrintDlgW.argtypes = [ctypes.POINTER(_PRINTDLGW)]
    cd.PrintDlgW.restype = wt.BOOL
    cd.CommDlgExtendedError.restype = wt.DWORD
    g.CreateDCW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p]
    g.CreateDCW.restype = wt.HDC
    g.GetDeviceCaps.argtypes = [wt.HDC, ctypes.c_int]
    g.StartDocW.argtypes = [wt.HDC, ctypes.POINTER(_DOCINFOW)]
    for ad in ("StartPage", "EndPage", "EndDoc", "AbortDoc", "DeleteDC"):
        getattr(g, ad).argtypes = [wt.HDC]
    g.SetStretchBltMode.argtypes = [wt.HDC, ctypes.c_int]
    g.SetBrushOrgEx.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    g.StretchDIBits.argtypes = [wt.HDC] + [ctypes.c_int] * 8 + [
        ctypes.c_char_p, ctypes.POINTER(_BITMAPINFOHEADER), wt.UINT, wt.DWORD]
    k32.GlobalLock.argtypes = [wt.HGLOBAL]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalUnlock.argtypes = [wt.HGLOBAL]
    k32.GlobalFree.argtypes = [wt.HGLOBAL]
    _gdi.hazir = (g, cd, k32)
    return _gdi.hazir


_KANCA = ctypes.WINFUNCTYPE(ctypes.c_size_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


def _ortala_kancasi(ana: int):
    """Yazdirma penceresini rubric'in ortasina koyup one getiren kanca.

    Pencereye sahip (hwndOwner) olarak rubric verilemiyor: sahip baska is
    parcaciginda (Tk'nin) olunca PrintDlg pencereyi hic kurmadan bekliyor
    (duz Tk ile de denendi). Sahipsiz acilinca da rubric'in arkasinda
    kalabilir; WM_INITDIALOG'da yerini ve odagi biz veriyoruz.
    """
    u32 = ctypes.windll.user32

    def kanca(hwnd, ileti, _wp, _lp):
        if ileti != 0x0110:                          # WM_INITDIALOG
            return 0
        a, d = wt.RECT(), wt.RECT()
        if u32.GetWindowRect(wt.HWND(ana), ctypes.byref(a)) and \
                u32.GetWindowRect(hwnd, ctypes.byref(d)):
            x = a.left + (a.right - a.left - (d.right - d.left)) // 2
            y = a.top + (a.bottom - a.top - (d.bottom - d.top)) // 3
            u32.SetWindowPos(hwnd, None, max(x, 0), max(y, 0), 0, 0, 0x1 | 0x4)  # NOSIZE NOZORDER
        u32.SetForegroundWindow(hwnd)
        return 1                                     # odagi ilk denetime varsayilan versin
    return _KANCA(kanca)


class _PRINTER_INFO_4W(ctypes.Structure):
    _fields_ = [("pPrinterName", wt.LPWSTR), ("pServerName", wt.LPWSTR),
                ("Attributes", wt.DWORD)]


def _yazicilar() -> list[str]:
    """Kurulu yazicilarin adlari (yerel + baglanti). Hata olursa bos liste."""
    try:
        ws = ctypes.WinDLL("winspool.drv")
        ws.EnumPrintersW.argtypes = [wt.DWORD, wt.LPWSTR, wt.DWORD, wt.LPBYTE,
                                     wt.DWORD, ctypes.POINTER(wt.DWORD),
                                     ctypes.POINTER(wt.DWORD)]
        gerek, sayi = wt.DWORD(0), wt.DWORD(0)
        bayrak = 0x2 | 0x4                      # LOCAL | CONNECTIONS
        ws.EnumPrintersW(bayrak, None, 4, None, 0, ctypes.byref(gerek), ctypes.byref(sayi))
        if not gerek.value:
            return []
        tampon = ctypes.create_string_buffer(gerek.value)
        if not ws.EnumPrintersW(bayrak, None, 4, ctypes.cast(tampon, wt.LPBYTE),
                                gerek.value, ctypes.byref(gerek), ctypes.byref(sayi)):
            return []
        dizi = ctypes.cast(tampon, ctypes.POINTER(_PRINTER_INFO_4W))
        return sorted({dizi[i].pPrinterName for i in range(sayi.value) if dizi[i].pPrinterName})
    except Exception:
        return []


def _varsayilan_yazici() -> str:
    """Windows'un varsayilan yazicisinin adi; tanimli degilse bos dize.

    Ilk cagri uzunlugu sorar, ikincisi adi yazar (Win32'nin her yerdeki
    kalibi). Yazici hic yoksa GetDefaultPrinter basarisiz doner.
    """
    try:
        ws = ctypes.WinDLL("winspool.drv")
        ws.GetDefaultPrinterW.argtypes = [wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
        ws.GetDefaultPrinterW.restype = wt.BOOL
        n = wt.DWORD(0)
        ws.GetDefaultPrinterW(None, ctypes.byref(n))
        if not n.value:
            return ""
        tampon = ctypes.create_unicode_buffer(n.value)
        if not ws.GetDefaultPrinterW(tampon, ctypes.byref(n)):
            return ""
        return tampon.value
    except Exception:
        return ""


def _yazici_adi(k32, hdevnames) -> str:
    """DEVNAMES'ten secilen yazicinin adi (wDeviceOffset karakter cinsinden)."""
    if not hdevnames:
        return ""
    p = k32.GlobalLock(hdevnames)
    if not p:
        return ""
    try:
        return ctypes.wstring_at(p + ctypes.c_ushort.from_address(p + 2).value * 2)
    finally:
        k32.GlobalUnlock(hdevnames)


def _dib(en: int, boy: int, ornek: bytes) -> bytes:
    """RGB ornekleri -> 24 bit DIB: BGR, alttan uste, satirlar 4 bayta hizali."""
    bgr = bytearray(ornek)
    bgr[0::3] = ornek[2::3]
    bgr[2::3] = ornek[0::3]
    satir = en * 3
    dolgu = bytes(-satir % 4)
    return b"".join(bgr[i * satir:(i + 1) * satir] + dolgu for i in range(boy - 1, -1, -1))


def _yazdirma_isi(hwnd: int, toplam: int, aktif: int, ad: str, cevap: queue.Queue,
                  kuyruk: queue.Queue, durdur: threading.Event,
                  yazici: str | None = None, cikti: str | None = None) -> None:
    """Yazdirma penceresi, sonra kuyruktan gelen sayfalari yaziciya basar.

    Haberler `cevap`a: ("secim", ilk, son, yazici, en, boy, dpi_x, dpi_y) ana
    is parcacigi sayfalari islemeye baslasin diye; ("sayfa", n); sonunda
    ("bitti", n, yazici) / ("iptal",) / ("hata", metin). Kuyruktaki oge
    (en, boy, rgb, x, y, hedef_en, hedef_boy); None bitti demek.
    """
    try:
        g, cd, k32 = _gdi()
        if yazici:
            hdc = g.CreateDCW("WINSPOOL", yazici, None, None)
            ilk, son = 1, toplam
            if not hdc:
                raise OSError(f"CreateDC: {yazici}")
        else:
            pd = _PRINTDLGW()
            pd.lStructSize = ctypes.sizeof(pd)
            kanca = _ortala_kancasi(hwnd)       # cagri bitene kadar referansi burada
            pd.lpfnPrintHook = ctypes.cast(kanca, ctypes.c_void_p)
            pd.Flags = (_PD_RETURNDC | _PD_NOSELECTION | _PD_USEDEVMODECOPIESANDCOLLATE
                        | _PD_HIDEPRINTTOFILE | _PD_ENABLEPRINTHOOK)
            pd.nMinPage, pd.nMaxPage = 1, min(toplam, 0xFFFF)
            pd.nFromPage = pd.nToPage = min(aktif, 0xFFFF)   # "Sayfalar" kutusunda bu sayfa
            pd.nCopies = 1
            tamam = cd.PrintDlgW(ctypes.byref(pd))
            kod = cd.CommDlgExtendedError()
            yazici = _yazici_adi(k32, pd.hDevNames)
            for tutamac in (pd.hDevMode, pd.hDevNames):
                if tutamac:
                    k32.GlobalFree(tutamac)
            if not tamam:
                cevap.put(("hata", f"PrintDlg 0x{kod:x}") if kod else ("iptal",))
                return
            hdc = pd.hDC
            if not hdc:
                raise OSError("PrintDlg: DC yok")
            ilk, son = (pd.nFromPage, pd.nToPage) if pd.Flags & _PD_PAGENUMS else (1, toplam)
    except Exception as e:
        cevap.put(("hata", str(e)))
        return

    belge_acik = False
    try:
        en, boy = g.GetDeviceCaps(hdc, 8), g.GetDeviceCaps(hdc, 10)       # HORZRES VERTRES
        dpx, dpy = g.GetDeviceCaps(hdc, 88), g.GetDeviceCaps(hdc, 90)     # LOGPIXELSX/Y
        bilgi = _DOCINFOW(ctypes.sizeof(_DOCINFOW), ad, cikti, None, 0)
        # Microsoft Print to PDF burada "farkli kaydet" sorar; vazgecilirse <= 0
        if g.StartDocW(hdc, ctypes.byref(bilgi)) <= 0:
            cevap.put(("iptal",))
            return
        belge_acik = True
        cevap.put(("secim", ilk, son, yazici, en, boy, dpx, dpy))
        g.SetStretchBltMode(hdc, 4)                                       # HALFTONE
        g.SetBrushOrgEx(hdc, 0, 0, None)
        n = 0
        while True:
            if durdur.is_set():
                g.AbortDoc(hdc)
                belge_acik = False
                cevap.put(("iptal",))
                return
            try:
                oge = kuyruk.get(timeout=0.2)
            except queue.Empty:
                continue
            if oge is None:
                break
            w, h, ornek, x, y, dw, dh = oge
            bas = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), w, h, 1, 24, 0)
            if g.StartPage(hdc) <= 0:
                raise OSError("StartPage")
            if g.StretchDIBits(hdc, x, y, dw, dh, 0, 0, w, h, _dib(w, h, ornek),
                               ctypes.byref(bas), 0, 0x00CC0020) in (0, -1):   # SRCCOPY
                raise OSError("StretchDIBits")
            if g.EndPage(hdc) <= 0:
                raise OSError("EndPage")
            n += 1
            cevap.put(("sayfa", n))
        belge_acik = False
        if g.EndDoc(hdc) <= 0:
            raise OSError("EndDoc")
        cevap.put(("bitti", n, yazici))
    except Exception as e:
        if belge_acik:
            g.AbortDoc(hdc)
        cevap.put(("hata", str(e)))
    finally:
        g.DeleteDC(hdc)


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
_pymupdf_bekle()                        # import edildi (testler, tus-karti.py)
