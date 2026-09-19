# -*- coding: utf-8 -*-
"""Testlerin ortak parcasi: depo kokunu yola ekler, deneme belgesi uretir.

Testler rubric.py'yi bu klasorun bir ustunden alir; nereden calistirildiklari
onemli degil. Deneme belgesi olarak RUBRIC_TEST_PDF ortam degiskeni verilmisse
o dosya kullanilir (gercek bir kitapta olcmek icin), yoksa icerigi bilinen
bir PDF gecici dizine uretilir:

    $env:RUBRIC_TEST_PDF = "D:\\kitaplar\\kalin-bir-kitap.pdf"
    uv run testler\\stres.py
"""

import os
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

# Her sayfada ayni satirlar; arama testleri bu kelimeleri arar.
METIN = [
    "the integral of a vector field along a closed curve",
    "a matrix acts on every vector of the space",
    "lorem ipsum dolor sit amet, consectetur adipiscing elit",
]


def yalit(rubric) -> str:
    """Veri ve ayar dizinini gecici bir dizine cevirir: test, kullanicinin
    durum.json'una ve rubricrc'sine dokunmasin."""
    gecici = tempfile.mkdtemp(prefix="rubric-test-")
    rubric.veri_dizini = lambda: gecici
    rubric.ayar_dizini = lambda: gecici
    return gecici


def deneme_pdf(sayfa: int = 40, ad: str = "deneme.pdf", ortamdan: bool = True) -> str:
    """Testin acacagi belgenin yolu.

    Uretilen belgede her sayfanin basinda numarasi, altinda METIN satirlari ve
    iki duzeyli icindekiler var (her 20 sayfada bolum, her 5 sayfada kisim).
    """
    yol = os.environ.get("RUBRIC_TEST_PDF")
    if ortamdan and yol:
        return yol

    import pymupdf

    hedef = os.path.join(tempfile.mkdtemp(prefix="rubric-belge-"), ad)
    belge = pymupdf.open()
    icindekiler = []
    for i in range(sayfa):
        s = belge.new_page(width=595, height=842)
        s.insert_text((72, 90), f"sayfa {i + 1} / {sayfa}", fontsize=18)
        for j, satir in enumerate(METIN):
            s.insert_text((72, 140 + 22 * j), satir, fontsize=12)
        if i % 20 == 0:
            icindekiler.append([1, f"bolum {i // 20 + 1}", i + 1])
        if i % 5 == 0:
            icindekiler.append([2, f"kisim {i // 5 + 1}", i + 1])
    belge.set_toc(icindekiler)
    belge.save(hedef, garbage=3, deflate=True)
    belge.close()
    return hedef
