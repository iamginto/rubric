# rubric

Zathura tadinda, vim tuslu bir belge okuyucu. Windows icin; arayuz tkinter,
sayfa isleme PyMuPDF (MuPDF).

Adini ortacag el yazmalarinda basliklarin yazildigi kirmizi murekkepten
(Latince *rubrica*) aliyor; varsayilan temasi da kirmizi fosfor.

PDF'in yani sira MuPDF'in actigi her sey: EPUB, XPS, CBZ, MOBI, FB2.

## Kurulum

Gerekenler: Windows 10 / 11 ve [uv](https://docs.astral.sh/uv/). Python 3.12'yi
uv kendisi kurar.

```powershell
uv sync
uv run rubric.py <dosya.pdf>
```

`uv run kisayol.py` masaustune ikonuyla bir **rubric** kisayolu kurar: cift tikla
acilir, konsol acmaz, uzerine PDF surukleyebilirsin. `.pdf` uzantisini bir
programa baglamak istersen `rubric.cmd` onun icin var.

Windows'un beyaz baslik cubugu yerine temaya uygun bir ust bar var:
`$ rubric <dosya>` ve `[-] [+] [x]`. Bardan (ya da alttaki durum cubugundan)
surukleyince pencere tasinir, cift tik buyutur, barin ust kenari boyutlandirir.
Bari `Ctrl-K` > `baslik-cubugu` ile ac / kapa; secim rubricrc'ye kalici yazilir.
Windows'un kendi basligini geri istersen `set windows-basligi true`.

Konsolsuz bir exe de uretilebilir (Python kurulumu gerektirmez, uzerine PDF
surukleyebilirsin):

```powershell
uv run --with pyinstaller exe-yap.py      # -> dist\rubric\rubric.exe
```

Exe yanindaki `_internal` klasoruyle birlikte calisir; baskasina vermek icin
`dist\rubric` klasorunu zip'le. Acilis ~0.3 sn; yalnizca yeni derlenmis exe'nin
ilk acilisi Defender taramasi yuzunden birkac saniye surer.

`uv run tus-karti.py` tus haritasinin PDF kartini masaustune
(`rubric-tuslari.pdf`) uretir. Kart tuslari `rubric.py`'deki haritadan okur, elle
yazilmaz - yani tus degisince kart da degisir.

## Tuslar

| | |
|---|---|
| `j` `k` `h` `l` | kaydir (oklar da olur) |
| `<C-d>` `<C-u>` | yarim ekran |
| `<Space>` `<C-f>` / `<C-b>` | tam ekran ileri / geri |
| `J` `K` | sonraki / onceki sayfa |
| `gg` `G` | ilk / son sayfa - `42G` ya da `42` Enter 42. sayfaya |
| `5j` | sayi oneki her komutta gecerli |
| `s` `a` | genislige / sayfaya sigdir |
| `+` `-` | yakinlastir - `<C-0>` %100 |
| `r` | 90 derece dondur |
| `<C-r>` | gece modu (renkleri ters cevir) |
| `d` | cift sayfa |
| `<Tab>` | icindekiler (`j/k/Enter/Esc`) |
| `<C-k>` | eylem paleti: komutlar, tuslari ve tus atama |
| `/` `?` | ileri / geri ara, `n` `N` gez, `<Esc>` eslemeleri kapat |
| `Shift`+surukle | metni vurgula; `v` kalemi acarsa duz surukleme de vurgular |
| sag tik | vurguyu sil - `u` son vurgu islemini geri alir |
| `V` | vurgu listesi (`j/k`, `Enter` git, `x` sil) |
| `:vurgulari-aktar` | `<ad>-vurgulu.pdf` kopyasi; asil PDF'e hic dokunulmaz |
| `m<harf>` `'<harf>` | isaret koy / isarete git |
| `<C-o>` `<C-i>` | ziplama gecmisinde geri / ileri |
| `<F11>` `<F5>` | tam ekran / sunum |
| `<C-m>` | durum cubugunu gizle |
| `o` | dosya ac, `R` yeniden yukle |
| `q` | bakilan belgeyi kapat (`Ctrl+W` de); sonuncusu kapaninca bos ekran |
| `<C-e>` | kapatilan belgeyi geri ac (Ctrl+E): kaldigi sayfa, zoom ve listedeki yeriyle; son 3 (1-10 ayarlanir) |
| `Q` | uygulamadan cik (Shift+q) - belgeler ve konumlar kaydedilir |
| `:` | komut satiri |

Fare: tekerlek kaydirir, `Ctrl`+tekerlek imlecin altindaki yeri sabit tutarak
yakinlastirir, surukleme sayfayi tasir.

## Komutlar

`:open <yol>` `:quit` `:reload` `:goto <n>` `:zoom <yuzde>` `:rotate`
`:set <anahtar> <deger>` `:map <tus> <komut>` `:unmap <tus>`
`:bmark <ad>` `:blist` `:bdelete <ad>` `:nohl` `:toc` `:info`
`:export <yol.png>` `:lang <en|tr|de>` `:rc` (yapilandirma dosyasinin yolu)
`:eylemler` `:help`

Kisaltmalar: `:q` `:o` `:e` `:r` `:bm` `:nohl`.

Ic komut adlari da dogrudan yazilabilir: `:sonraki-sayfa`.

## Eylem paleti (`<C-k>`)

Tus degistirmek icin dosya bulup elle duzenlemek gerekmiyor. `<C-k>` butun ic
komutlari, ne ise yaradiklarini ve o anki tuslarini tek listede acar:

```
> gece
[ yakinlastirma ve duzen ]
  ters-renk    gece modu: renkleri ters cevir              <C-r>
```

Yazdikca suzulur (ad, aciklama ya da tus uzerinden), `<Down>`/`<Up>` gezer,
`Enter` komutu calistirir. Secili komutun uzerinde yine `<C-k>` sag altta
eylemleri acar:

| | |
|---|---|
| `calistir` | komutu calistir |
| `tus ata` | bir tus bileskesine bas, `Enter` ile onayla |
| `tusu kaldir` | birden cok tus varsa hangisi diye sorar |
| `varsayilana don` | komutun varsayilan tuslarini geri getirir |

Onay ekrani ne olacagini basmadan once soyler: tus baska bir komuttaysa kimden
alinacagini, sayi tusu gibi calismayacak bir sey sectiysen nedenini yazar.
`Esc` vazgecer.

Atama **kalici**: `%APPDATA%\rubric\rubricrc` dosyasinin sonundaki isaretli bloga
yazilir. Elle yazdigin satirlara dokunulmaz, varsayilanina donen tus blokta yer
tutmaz. Yani palet ile dosya ayni seyi soyler, biri otekini ezmez.

## Belge listesi ve oturum

Actigin belgeler acilis sirasiyla bir listede durur: `Ctrl+Right` sonraki
(daha yeni), `Ctrl+Left` onceki (daha eski), uclarda basa doner. `B` listeyi
acar (`Enter` git, `x` kapat), `q` (ya da `Ctrl+W`) bakilan belgeyi kapatir;
uygulamadan cikmak `Q`. Yanlislikla kapattigini `Ctrl+E` geri acar
(son 3 tane, en yenisi once; uygulamayi kapatip acsan da). Kac tane
olacagini `Ctrl+K` > ayarlar > `geri-acma-siniri` listesinden 1-10 arasi
secersin; secim rubricrc'ye `set kapanan-belgeler` olarak yazilir.
Dosya penceresinde birden cok dosya secilebilir. Durum cubugunda `[2/3]`.

Uygulamayi kapatip acinca liste ve son baktigin belge, kaldigin sayfayla geri
gelir (`set oturum false` kapatir). zathura'daki gibi bellekte yalnizca bakilan
belge acik; digerleri yol + kaldigin yer. Liste `son-belgeler` (varsayilan 10,
zathura'nin `show-recent`'i gibi) ile sinirli: dolunca en uzun suredir
bakmadigin belge cikar, silinmis dosyalar acilista ayiklanir.

## Temalar

`Ctrl+K` > en alttaki `tema` > Enter: dil secimi gibi bir liste acilir, on tema
her biri kendi renginde, secili olan `[x]`. `j/k` ile gez, `Enter` uygular ve
rubricrc'ye `set tema <ad>` yazar; palet acik kalir, baska tema icin yine Enter.
`:tema` listeyi acar, `:tema neon` dogrudan gecer
(her dildeki ad olur: `:theme ice`). Temalar: kirmizi-fosfor (varsayilan),
yesil-fosfor, kehribar, buz, neon, kutup-gecesi, toprak, murekkep, kagit,
gun-isigi. rubricrc'de elle yazilan tek bir renk (`set vurgu #...`), satir
sirasindan bagimsiz olarak her temanin ustunde kalir.

## Dil / Language / Sprache

Arayuz Ingilizce (varsayilan), Turkce ve Almanca. Degistirmek icin `<C-k>` >
`dil` > Enter: English / Türkçe / Deutsch listesinden secilir. `:lang` da ayni
listeyi acar, `:lang tr` dogrudan gecer. Secim rubricrc'ye `set dil tr` olarak
kalici yazilir. Tus karti da ayni dili konusur: `uv run tus-karti.py --dil de`.

The interface speaks English (default), Turkish and German: `<C-k>` >
`language` > Enter opens a picker, `:lang` does the same, `:lang de` switches
directly. Command names are translated too (`scroll-down` / `aşağı` /
`runter`) and a name from any language works everywhere: `:next-page`,
`map x nächste-seite` in rubricrc. The palette always writes the internal id
to rubricrc so switching languages never breaks the file. Setting names
(`set ters-renk`) are not translated.

Palette aksansiz yazmak da bulur (`sigdir` -> "sığdır"). Yazitipi yoksa
Consolas / Cascadia Mono / DejaVu Sans Mono / Courier New'den ilk bulunana
dusulur; hepsi Turkce ve Almanca harflerin tamamini tasir.

## Yapilandirma

`rubricrc.ornek` dosyasini `%APPDATA%\rubric\rubricrc` yoluna kopyala. Icinde her
ayarin ne ise yaradigi ve baglanabilecek butun ic komutlarin listesi var.
Calisirken denemek icin `:set`, kalici yapmak icin dosyaya yaz.

Durum cubugunun metni de ayar:

```
set durum-bicimi  $ {ad} :: {sayfa}/{toplam} [{yuzde}%] z{zoom}%{ters}{arama}
```

Bozuk bir satir yalnizca kendini dusurur; uygulama acilir, hata durum
cubugunda gorunur.

## Nasil calisiyor

- **Render**: PyMuPDF sayfayi PPM'e verir, tkinter `PhotoImage` onu dogrudan
  okur - Pillow'a gerek yok.
- **Kaydirma**: butun sayfalar tek bir uzun tuvale dizilir, ama yalnizca
  goruntuye girenler islenir; cikanlar tuvalden dusurulur. 1612 sayfalik bir
  kitap 0.6 sn'de aciliyor, bellekte hep 12 sayfa duruyor.
- **Konum**: mutlak piksel yerine (sayfa, sayfa icindeki oran) ikilisi
  saklanir. Bu yuzden yakinlastirinca, pencereyi boyutlandirinca ya da cift
  sayfaya gecince bakilan yer kaymaz; isaretler ve "kaldigi yerden ac" da
  ayni ikiliyi kullanir.
- **Yakinlastirma**: tekerlek / tus olayi yalnizca hedef zoom'u gunceller;
  kuyrukta olay kalmayinca birikenler tek cizimde uygulanir ve once yalnizca
  gorunen sayfalar islenir. Hizli cevrilen tekerlek boylece geride kalmaz
  (1612 sayfada 6 tik: 1.2 sn -> 70 ms).
- **Arama** imlecin oldugu sayfadan baslar, basa sarar ve 6 sayfalik partiler
  halinde arka planda yurur. Ilk esleme ~170 ms'de bulunur, geri kalani
  dolarken arayuz calisir. (Tek seferde taramak 1612 sayfada 20 sn donduruyordu.)

## Veriler nerede

| | |
|---|---|
| `%APPDATA%\rubric\rubricrc` | yapilandirma (elle ya da eylem paletinden) |
| `%LOCALAPPDATA%\rubric\durum.json` | dosya basina son okunan yer, isaretler, yer imleri ve vurgular |

`durum.json` acilan belgelerin tam yolunu ve vurgulanan metni de tutar; okuma
gecmisini silmek icin bu dosyayi sil. rubric internete hic baglanmaz, belgedeki
baglantilari ve gomulu betikleri calistirmaz. Vurgular asil PDF'e yazilmaz;
yalnizca `:vurgulari-aktar` ayri bir kopya uretir.

## Testler

`testler\` altindaki betikler arayuzu `mainloop` cagirmadan kurar ve komutlari
dogrudan surer. Gecici bir veri / ayar dizini ve kendi urettikleri bir deneme
PDF'i kullanirlar; gercek `rubricrc` ve `durum.json`'a dokunmazlar.

```powershell
uv run testler\duman.py      # butun komutlari sirayla surer, hata sayar
uv run testler\palet.py      # eylem paleti: gezinme, tus atama, rubricrc
uv run testler\vurgu.py      # metin vurgulari, kalicilik, aktarma
uv run testler\rc.py         # rubricrc okuyucusu ve rubricrc.ornek
uv run testler\sayfa_git.py  # 42 Enter
uv run testler\zoom.py       # yakinlastirma: olay birlestirme, imlec capasi, sure
uv run testler\icindekiler.py  # panel: dogru basliktan acilma, oklar, hatirlama
uv run testler\cerceve.py    # pencere cercevesi ve ust bar (ekrandan okur)
uv run testler\stres.py      # 1612 sayfada acilis / kaydirma olcumu
uv run testler\arama.py      # parcali aramanin arayuzu dondurmedigini olcer
```

Gercek bir kitapta olcmek icin `$env:RUBRIC_TEST_PDF = "<yol.pdf>"`.

`testler\fare.py` ayridir: isletim sistemine gercek fare ve klavye girdisi
verir, ~30 sn boyunca imleci ve klavyeyi ele gecirir. Calisirken bilgisayara
dokunma.

## Lisans

[GNU AGPL-3.0](LICENSE) ya da sonraki bir surumu. rubric, yine AGPL-3.0
lisansli [PyMuPDF](https://github.com/pymupdf/PyMuPDF) uzerine kurulu.
Degistirilmis bir surumunu (exe dahil) dagitan, kaynak kodunu da ayni
lisansla vermek zorunda.
