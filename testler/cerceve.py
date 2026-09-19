# -*- coding: utf-8 -*-
"""Pencere cercevesi ve temali ust bar: Windows basligi, ust bar ac/kapa
(rubricrc'ye kalici), tam ekrandan donus, ad kisaltma, dugmeler."""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import tempfile

import ortak  # depo kokunu yola ekler; rubric'ten once gelmeli
import rubric

GECICI = tempfile.mkdtemp(prefix="rubric-cerceve-")
rubric.veri_dizini = lambda: GECICI
rubric.ayar_dizini = lambda: GECICI
RC = os.path.join(GECICI, "rubricrc")
# ust barda ortadan kisaltilacak kadar uzun bir ad (RUBRIC_TEST_PDF'e bakilmaz)
PDF = ortak.deneme_pdf(3, "cok uzun bir belge adi - ust barda ortadan kisaltilmasi "
                          "gereken deneme dosyasi (1920 x 3240).pdf", ortamdan=False)

hata = []


def dogru(ne, kosul, ek=""):
    if not kosul:
        hata.append(ne)
    print(f"  [{'x' if kosul else ' '}] {ne}" + (f"   {ek}" if ek else ""))


u32 = rubric._win32()[0]


def durum(u):
    u.update()
    hwnd = wt.HWND(int(u.wm_frame(), 16))
    stil = u32.GetWindowLongPtrW(hwnd, -16)
    dis = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(dis))
    return {
        "windows": stil & rubric._WS_CAPTION == rubric._WS_CAPTION,
        "bar": bool(u.ust_bar.winfo_ismapped()),
        "ust_pay": u.winfo_rooty() - dis.top,
    }


class Olay:
    def __init__(self, w, x=3, y=3):
        self.widget, self.x, self.y = w, x, y


u = rubric.Rubric(PDF if os.path.exists(PDF) else None)
u.geometry("700x500+150+150")
d = durum(u)
print("acilis:", d)
dogru("Windows basligi yok", not d["windows"])
dogru("temali bar gorunuyor", d["bar"])
dogru("bar pencerenin en tepesinde", d["ust_pay"] == 0 and u.ust_bar.winfo_y() == 0,
      f"pay {d['ust_pay']}  bar y {u.ust_bar.winfo_y()}")
dogru("bar tuvalin ustunde", u.ust_bar.winfo_y() < u.tuval.winfo_y())

print("\n-- ust kenarda gri serit yok (odak kaybi, baslik, ikon) --")
gdi = ctypes.windll.gdi32
u32.GetDC.restype = wt.HDC
u32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
gdi.GetPixel.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
u.attributes("-topmost", True)


def ust_satirlar():
    """Pencerenin ust 8 satiri, ekrandan, fiziksel piksel. Serit varken
    okunan: 'ffffff f4f7fc f4f7fc ...' (pasif) / 'ffffff b4b4b4 ...' (aktif)."""
    import time
    for _ in range(4):                      # boyama bitsin
        u.update()
        time.sleep(0.05)
    hwnd = wt.HWND(int(u.wm_frame(), 16))
    eski = u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    dc = u32.GetDC(None)
    satirlar = [gdi.GetPixel(dc, (r.left + r.right) // 2, y) for y in range(r.top, r.top + 8)]
    u32.ReleaseDC(None, dc)
    u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(eski))
    return satirlar


def acik_renk_var(satirlar):
    # 0. satir DWM'nin kenar cizgisi. Serit 1-6. satirlara boyanir; 7'den
    # sonrasi barin yazisina denk gelebilir, o yuzden bakilmaz.
    var = any(sum((c >> k) & 0xFF for k in (0, 8, 16)) > 3 * 0x60 for c in satirlar[1:7])
    if var or "-v" in sys.argv:
        print("      satirlar:", " ".join(f"{c & 0xFF:02x}{(c >> 8) & 0xFF:02x}{(c >> 16) & 0xFF:02x}"
                                          for c in satirlar))
    return var


hwnd_ = wt.HWND(int(u.wm_frame(), 16))
dogru("acilista serit yok", not acik_renk_var(ust_satirlar()))
u32.PostMessageW(hwnd_, 0x0086, 0, 0)      # WM_NCACTIVATE(FALSE): odak kaybi
dogru("odak kaybinda serit yok", not acik_renk_var(ust_satirlar()))
u32.PostMessageW(hwnd_, 0x0086, 1, 0)
dogru("odak geri gelince serit yok", not acik_renk_var(ust_satirlar()))
u.title("deneme basligi - rubric")           # WM_SETTEXT: her sayfa degisiminde olur
dogru("baslik degisince serit yok", not acik_renk_var(ust_satirlar()))
tampon = ctypes.create_unicode_buffer(128)
u32.GetWindowTextW(hwnd_, tampon, 128)
dogru("baslik yine de degisti (gorev cubugu)", tampon.value == "deneme basligi - rubric",
      repr(tampon.value))
u.iconbitmap(default=os.path.join(ortak.KOK, "rubric.ico"))   # WM_SETICON
dogru("ikon ayarlaninca serit yok", not acik_renk_var(ust_satirlar()))
u.durumu_tazele()

print("\n-- ad kisaltma --")
metin = u.ust_ad.cget("text")
print("   |", metin)
if os.path.exists(PDF):
    dogru("uzun ad kisaldi", "..." in metin)
    dogru("uzanti gorunuyor", metin.endswith(".pdf"))
    dogru("dugmelere tasmiyor",
          u.ust_ad.winfo_x() + rubric.tkfont.Font(font=u.ust_ad.cget("font")).measure(metin)
          <= u.ust_dugmeler["kucult"].winfo_x())

print("\n-- palet komutu: ac / kapa, kalici --")
u.calistir("baslik-cubugu")
d = durum(u)
dogru("komutla bar gizlendi", not d["bar"])
dogru("tuval en tepeye cikti", u.tuval.winfo_y() == 0)
icerik = open(RC, encoding="utf-8").read()
dogru("rubricrc'ye yazildi", "set baslik-cubugu false" in icerik)
u.calistir("baslik-cubugu")
d = durum(u)
dogru("komutla geri geldi", d["bar"] and u.ust_bar.winfo_y() == 0)
icerik = open(RC, encoding="utf-8").read()
dogru("rubricrc guncellendi (tek satir)", icerik.count("set baslik-cubugu") == 1
      and "set baslik-cubugu true" in icerik)

yeni = rubric.Yapilandirma()
yeni.yukle(RC)
dogru("rubricrc geri okununca ayar dogru", yeni.ayar["baslik-cubugu"] is True)

print("\n-- tam ekran / sunum --")
u.calistir("tam-ekran")
u.update()
dogru("tam ekranda bar gizli", not u.ust_bar.winfo_ismapped())
u.calistir("tam-ekran")
d = durum(u)
dogru("tam ekrandan donunce bar ve cerceve eski halinde",
      d["bar"] and not d["windows"] and d["ust_pay"] == 0, str(d))
u.calistir("sunum")
u.update()
dogru("sunumda bar gizli", not u.ust_bar.winfo_ismapped())
u.calistir("sunum")
d = durum(u)
dogru("sunumdan donunce bar geri", d["bar"] and not d["windows"], str(d))

print("\n-- dugmeler --")
u._dugme_tiklandi(Olay(u.ust_dugmeler["buyut"]), "buyut")
u.update()
dogru("[+] buyuttu", u.state() == "zoomed")
dogru("dugme [=] oldu", u.ust_dugmeler["buyut"].cget("text") == "[=]")
u._dugme_tiklandi(Olay(u.ust_dugmeler["buyut"]), "buyut")
u.update()
dogru("[=] geri aldi", u.state() == "normal" and u.ust_dugmeler["buyut"].cget("text") == "[+]")
u._dugme_tiklandi(Olay(u.ust_dugmeler["kucult"]), "kucult")
u.update()
dogru("[-] simge durumuna kucultu", u.state() == "iconic", u.state())
u.deiconify()
u.update()
u._dugme_tiklandi(Olay(u.ust_dugmeler["buyut"], x=-50), "buyut")
dogru("disarida birakilan tik bir sey yapmadi", u.state() == "normal")
u._dugme_uzerinde("kapat", True)
dogru("[x] uzerinde hata renginde", u.ust_dugmeler["kapat"].cget("fg") == u.ayar["hata"])
u._dugme_uzerinde("kapat", False)

print("\n-- ust kenar --")


class KenarOlayi:
    def __init__(self, dx, dy):
        self.x_root, self.y_root = u.winfo_rootx() + dx, u.winfo_rooty() + dy


dogru("ust kenar HTTOP", u._ust_kenar(KenarOlayi(200, 1)) == 12)
dogru("sol ust kose HTTOPLEFT", u._ust_kenar(KenarOlayi(2, 1)) == 13)
dogru("sag ust kose HTTOPRIGHT", u._ust_kenar(KenarOlayi(u.winfo_width() - 2, 1)) == 14)
dogru("barin ortasi tasima", u._ust_kenar(KenarOlayi(200, 12)) is None)

print("\n-- Windows basligi ayri ayar --")
u.komutu_isle("set windows-basligi true")
d = durum(u)
dogru(":set windows-basligi true", d["windows"] and d["ust_pay"] > 20, str(d))
dogru("Windows basligi varken ust kenar yakalanmaz", u._ust_kenar(KenarOlayi(200, 1)) is None)
u.komutu_isle("set windows-basligi false")
d = durum(u)
dogru("geri kapandi", not d["windows"] and d["ust_pay"] == 0, str(d))

u.cik()
print("\nHATA SAYISI:", len(hata))
