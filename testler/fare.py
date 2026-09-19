# -*- coding: utf-8 -*-
"""Gercek fare girdisiyle pencere testi: bar / durum cubugundan surukleme,
cift tik ile buyutme, ust kenardan boyutlandirma.

    uv run testler\\fare.py

Diger testler Tk'nin icinden olay uretir; bu ise isletim sistemine gercek
fare girdisi (SendInput) verir, yani kullanicinin eliyle yaptiginin aynisi.
Birkac saniye boyunca imleci kendisi oynatir - o arada fareye dokunma.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time

import ortak

KOK = ortak.KOK
PDF = ortak.deneme_pdf(40)
BILGI = os.path.join(os.environ["TEMP"], "rubric-fare-bilgi.json")

u32 = ctypes.windll.user32
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # fiziksel piksel
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.IsZoomed.argtypes = [wt.HWND]

hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("_pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def fare(bayrak):
    girdi = INPUT(type=0)
    girdi.mi = MOUSEINPUT(0, 0, 0, bayrak, 0, 0)
    u32.SendInput(1, ctypes.byref(girdi), ctypes.sizeof(INPUT))


def git(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.02)


AYRINTI = "-v" in sys.argv


def surukle(x0, y0, dx, dy, adim=25, bekle=0.25):
    git(x0, y0)
    time.sleep(0.15)
    if AYRINTI:
        print(f"    {time.perf_counter():.3f} bas {int(x0)},{int(y0)}")
    fare(0x0002)                                   # sol tus bas
    time.sleep(bekle)
    for i in range(1, adim + 1):
        git(x0 + dx * i / adim, y0 + dy * i / adim)
    time.sleep(0.2)
    fare(0x0004)                                   # birak
    if AYRINTI:
        print(f"    {time.perf_counter():.3f} birak")
    time.sleep(0.6)


def cift_tik(x, y):
    git(x, y)
    time.sleep(0.15)
    for _ in range(2):
        fare(0x0002)
        fare(0x0004)
        time.sleep(0.05)
    time.sleep(0.8)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


def tus(vk, birak=False):
    girdi = INPUT(type=1)
    ctypes.memmove(ctypes.addressof(girdi.u), ctypes.byref(
        KEYBDINPUT(vk, 0, 0x0002 if birak else 0, 0, 0)), ctypes.sizeof(KEYBDINPUT))
    u32.SendInput(1, ctypes.byref(girdi), ctypes.sizeof(INPUT))
    time.sleep(0.03)


def bas(*vkler):
    """Bileske: bas(0x11, 0x4B) = Ctrl+K."""
    for vk in vkler:
        tus(vk)
    for vk in reversed(vkler):
        tus(vk, birak=True)
    time.sleep(0.25)


def yaz(metin):
    """Klavye duzeninden bagimsiz: harfler Unicode paketi olarak gider
    (Turkce Q'da VK_I 'ı' uretir, o yuzden VK ile yazilmaz)."""
    for harf in metin:
        for bayrak in (0x0004, 0x0004 | 0x0002):             # UNICODE, UNICODE|KEYUP
            girdi = INPUT(type=1)
            ctypes.memmove(ctypes.addressof(girdi.u), ctypes.byref(
                KEYBDINPUT(0, ord(harf), bayrak, 0, 0)), ctypes.sizeof(KEYBDINPUT))
            u32.SendInput(1, ctypes.byref(girdi), ctypes.sizeof(INPUT))
        time.sleep(0.03)
    time.sleep(0.25)


def bilgi():
    time.sleep(0.4)                                            # uygulama 150 ms'de bir yazar
    for _ in range(5):
        try:
            return json.load(open(BILGI, encoding="utf-8"))
        except (ValueError, OSError):
            time.sleep(0.1)
    return {}


def dikdortgen(hwnd):
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


if os.path.exists(BILGI):
    os.remove(BILGI)
uygulama = subprocess.Popen([os.path.join(KOK, ".venv", "Scripts", "pythonw.exe"),
                             os.path.join(KOK, "testler", "fare_uygulama.py"),
                             PDF if os.path.exists(PDF) else "-", BILGI, "30000"],
                            stderr=subprocess.PIPE)
for _ in range(100):
    if os.path.exists(BILGI):
        break
    time.sleep(0.1)
time.sleep(1.0)
b = json.load(open(BILGI, encoding="utf-8"))
hwnd = wt.HWND(b["hwnd"])
eski_imlec = wt.POINT()
u32.GetCursorPos(ctypes.byref(eski_imlec))

try:
    L, T, R, B = dikdortgen(hwnd)
    olcek = (R - L) / b["gen"]                     # mantiksal -> fiziksel
    print(f"pencere {L},{T}-{R},{B}  olcek {olcek:.2f}  bar {b['bar_h']} px")

    def bar_nokta(x_oran=0.45):
        L, T, R, B = dikdortgen(hwnd)
        return L + (R - L) * x_oran, T + (b["bar_y"] + b["bar_h"] / 2) * olcek

    print("\n-- ust bardan surukle --")
    x, y = bar_nokta()
    once = dikdortgen(hwnd)
    surukle(x, y, 180, 120)
    sonra = dikdortgen(hwnd)
    dogru("pencere tasindi", (sonra[0] - once[0], sonra[1] - once[1]) != (0, 0),
          f"{once[:2]} -> {sonra[:2]}")
    dogru("imlecle birlikte ~(180,120) gitti",
          abs(sonra[0] - once[0] - 180) < 12 and abs(sonra[1] - once[1] - 120) < 12,
          f"fark {sonra[0] - once[0]},{sonra[1] - once[1]}")
    dogru("boyut degismedi", (sonra[2] - sonra[0], sonra[3] - sonra[1]) ==
          (once[2] - once[0], once[3] - once[1]))

    print("\n-- dosya adinin uzerinden surukle --")
    once = dikdortgen(hwnd)
    L, T, R, B = once
    surukle(L + (b["ad_x"] + 30) * olcek, bar_nokta()[1], -120, -60)
    sonra = dikdortgen(hwnd)
    dogru("ad etiketinden de tasiniyor", abs(sonra[0] - once[0] + 120) < 12
          and abs(sonra[1] - once[1] + 60) < 12, f"fark {sonra[0] - once[0]},{sonra[1] - once[1]}")

    print("\n-- durum cubugundan surukle --")
    once = dikdortgen(hwnd)
    L, T, R, B = once
    surukle(L + (R - L) * 0.5, T + (b["cubuk_y"] + b["cubuk_h"] / 2) * olcek, -100, 50)
    sonra = dikdortgen(hwnd)
    dogru("durum cubugundan tasindi", abs(sonra[0] - once[0] + 100) < 12
          and abs(sonra[1] - once[1] - 50) < 12, f"fark {sonra[0] - once[0]},{sonra[1] - once[1]}")

    print("\n-- cift tik --")
    cift_tik(*bar_nokta())
    dogru("cift tik buyuttu", bool(u32.IsZoomed(hwnd)))
    cift_tik(*bar_nokta())
    dogru("ikinci cift tik geri aldi", not u32.IsZoomed(hwnd))

    print("\n-- buyukken surukleyince eski boyuta donup tasinmali --")
    cift_tik(*bar_nokta())
    x, y = bar_nokta()
    surukle(x, y, 60, 200)
    dogru("surukleme buyutmeyi birakti", not u32.IsZoomed(hwnd))

    print("\n-- ust kenardan boyutlandir --")
    once = dikdortgen(hwnd)
    L, T, R, B = once
    surukle(L + (R - L) * 0.5, T + 1, 0, -70)
    sonra = dikdortgen(hwnd)
    dogru("ust kenar yukari cekildi, pencere uzadi",
          sonra[1] < once[1] - 30 and sonra[3] == once[3],
          f"ust {once[1]} -> {sonra[1]}, alt {once[3]} -> {sonra[3]}")

    print("\n-- yan kenardan boyutlandir --")
    once = dikdortgen(hwnd)
    L, T, R, B = once
    surukle(R - 2, T + (B - T) * 0.5, 80, 0)
    sonra = dikdortgen(hwnd)
    dogru("sag kenar genisledi", sonra[2] > once[2] + 40, f"sag {once[2]} -> {sonra[2]}")

    print("\n-- tiklama (surukleme degil) --")
    once = dikdortgen(hwnd)
    git(*bar_nokta(0.3))
    fare(0x0002)
    fare(0x0004)
    time.sleep(0.5)
    dogru("tek tik pencereyi oynatmadi", dikdortgen(hwnd) == once)
    time.sleep(0.5)

    # --- gercek klavye: odak once tuvale (tik), sonra tuslar ---
    L, T, R, B = dikdortgen(hwnd)
    git(L + (R - L) * 0.5, T + (B - T) * 0.5)
    fare(0x0002)
    fare(0x0004)
    time.sleep(0.4)

    print("\n-- Ctrl+K paleti, bari kapat / ac --")
    bas(0x11, 0x4B)
    d = bilgi()
    dogru("Ctrl+K paleti acti", d.get("mod") == "palet", str(d.get("mod")))
    yaz("baslik-cubugu")
    bas(0x0D)
    d = bilgi()
    dogru("paletten bar kapandi", d.get("bar") is False and d.get("mod") == "normal",
          f"bar={d.get('bar')} mod={d.get('mod')}")
    bas(0x11, 0x4B)
    yaz("baslik-cubugu")
    bas(0x0D)
    d = bilgi()
    dogru("paletten bar geri acildi", d.get("bar") is True, f"bar={d.get('bar')}")
    bas(0x11, 0x4B)
    bas(0x1B)
    d = bilgi()
    dogru("Esc paleti kapatti", d.get("mod") == "normal", str(d.get("mod")))

    print("\n-- sayi + Enter --")
    bas(0x31)                                   # rakamlar VK ile: gercek klavye gibi
    bas(0x32)
    bas(0x0D)
    d = bilgi()
    dogru("12 Enter -> 12. sayfa", d.get("sayfa") == 12, f"sayfa {d.get('sayfa')}")
    yaz("5")                                    # Unicode paketi (ekran klavyesi, AHK)
    bas(0x0D)
    d = bilgi()
    dogru("5 Enter -> 5. sayfa", d.get("sayfa") == 5, f"sayfa {d.get('sayfa')}")

    print("\n-- F11 tam ekran, F5 sunum --")
    bas(0x7A)
    d = bilgi()
    dogru("F11 tam ekran", d.get("tam") is True and d.get("bar") is False, str(d.get("tam")))
    bas(0x7A)
    d = bilgi()
    dogru("F11 geri, bar yerinde", d.get("tam") is False and d.get("bar") is True)
    bas(0x74)
    d = bilgi()
    dogru("F5 sunum", d.get("tam") is True)
    bas(0x74)
    d = bilgi()
    dogru("F5 geri", d.get("tam") is False and d.get("bar") is True)

    print("\n-- tam ekrandan sonra surukleme hala calisiyor mu --")
    time.sleep(0.4)
    # Tk tam ekrana girip cikarken sarmalayici pencereyi yeniden kurar: HWND degisir.
    hwnd = wt.HWND(bilgi()["hwnd"])
    once = dikdortgen(hwnd)
    x, y = bar_nokta()
    u32.WindowFromPoint.argtypes = [wt.POINT]
    u32.WindowFromPoint.restype = wt.HWND
    u32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
    u32.GetAncestor.restype = wt.HWND
    ust = u32.GetAncestor(u32.WindowFromPoint(wt.POINT(int(x), int(y))), 2)   # GA_ROOT
    stil = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
    dis_stil = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    d = bilgi()
    print(f"  tiklanacak nokta {int(x)},{int(y)}  pencere {once}  "
          f"noktadaki pencere rubric mi: {ust == hwnd.value}  stil {stil & 0xFFFFFFFF:#x}  "
          f"exstil {dis_stil & 0xFFFFFFFF:#x}  bar_y {d.get('bar_y')}  durum {d.get('durum')}")
    surukle(x, y, -90, -40)
    sonra = dikdortgen(hwnd)
    dogru("F11/F5 sonrasi bardan tasiniyor", abs(sonra[0] - once[0] + 90) < 12
          and abs(sonra[1] - once[1] + 40) < 12, f"fark {sonra[0] - once[0]},{sonra[1] - once[1]}")
finally:
    fare(0x0004)
    u32.SetCursorPos(eski_imlec.x, eski_imlec.y)
    cokmus = uygulama.poll() is not None
    uygulama.kill()
    dogru("uygulama butun test boyunca ayakta kaldi", not cokmus)
    if "-v" in sys.argv and os.path.exists(BILGI + ".kayit"):
        print("\n-- uygulama kaydi --")
        print(open(BILGI + ".kayit", encoding="utf-8").read())
    hata_metni = uygulama.stderr.read().decode("utf-8", "replace").strip()
    if hata_metni:
        print("  uygulamanin stderr'i:\n    " + hata_metni.replace("\n", "\n    ")[:1500])

print("\nHATA SAYISI:", len(hata))
