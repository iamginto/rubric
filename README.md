# rubric

Zathura tadında, vim tuşlu bir belge okuyucu. Windows için; arayüz tkinter,
sayfa işleme PyMuPDF (MuPDF).

Adını ortaçağ el yazmalarında başlıkların yazıldığı kırmızı mürekkepten
(Latince *rubrica*) alıyor; varsayılan teması da kırmızı fosfor.

PDF'in yanı sıra MuPDF'in açtığı her şey: EPUB, XPS, CBZ, MOBI, FB2.

## Kurulum

Gerekenler: Windows 10 / 11 ve [uv](https://docs.astral.sh/uv/). Python 3.12'yi
uv kendisi kurar.

```powershell
uv sync
uv run rubric.py <dosya.pdf>
```

`uv run kisayol.py` masaüstüne ikonuyla bir **rubric** kısayolu kurar: çift tıkla
açılır, konsol açmaz, üzerine PDF sürükleyebilirsin. `.pdf` uzantısını bir
programa bağlamak istersen `rubric.cmd` onun için var.

Windows'un beyaz başlık çubuğu yerine temaya uygun bir üst bar var:
`$ rubric <dosya>` ve `[-] [+] [x]`. Bardan (ya da alttaki durum çubuğundan)
sürükleyince pencere taşınır, çift tık büyütür, barın üst kenarı boyutlandırır.
Barı `Ctrl-K` > `baslik-cubugu` ile aç / kapa; seçim rubricrc'ye kalıcı yazılır.
Windows'un kendi başlığını geri istersen `set windows-basligi true`.

Konsolsuz bir exe de üretilebilir (Python kurulumu gerektirmez, üzerine PDF
sürükleyebilirsin):

```powershell
uv run --with pyinstaller exe-yap.py      # -> dist\rubric\rubric.exe
```

Exe yanındaki `_internal` klasörüyle birlikte çalışır; başkasına vermek için
`dist\rubric` klasörünü zip'le. Açılış ~0.3 sn; yalnızca yeni derlenmiş exe'nin
ilk açılışı Defender taraması yüzünden birkaç saniye sürer.

`uv run tus-karti.py` tuş haritasının PDF kartını masaüstüne
(`rubric-tuslari.pdf`) üretir. Kart, tuşları `rubric.py`'deki haritadan okur;
elle yazılmaz, yani tuş değişince kart da değişir.

## Tuşlar

| | |
|---|---|
| `j` `k` `h` `l` | kaydır (oklar da olur) |
| `<C-d>` `<C-u>` | yarım ekran |
| `<Space>` `<C-f>` / `<C-b>` | tam ekran ileri / geri |
| `J` `K` | sonraki / önceki sayfa |
| `gg` `G` | ilk / son sayfa - `42G` ya da `42` Enter 42. sayfaya |
| `5j` | sayı öneki her komutta geçerli |
| `s` `a` | genişliğe / sayfaya sığdır |
| `+` `-` | yakınlaştır - `<C-0>` %100 |
| `r` | 90 derece döndür |
| `<C-r>` | gece modu (renkleri ters çevir) |
| `d` | çift sayfa |
| `<Tab>` | içindekiler (`j/k/Enter/Esc`) |
| `<C-k>` | eylem paleti: komutlar, tuşları ve tuş atama |
| `/` `?` | ileri / geri ara, `n` `N` gez, `<Esc>` eşleşmeleri kapat |
| `Shift`+sürükle | metni vurgula; `v` kalemi açarsa düz sürükleme de vurgular |
| sağ tık | vurguyu sil - `u` son vurgu işlemini geri alır |
| `V` | vurgu listesi (`j/k`, `Enter` git, `x` sil) |
| `:vurgulari-aktar` | `<ad>-vurgulu.pdf` kopyası; asıl PDF'e hiç dokunulmaz |
| `m<harf>` `'<harf>` | işaret koy / işarete git |
| `<C-o>` `<C-i>` | zıplama geçmişinde geri / ileri |
| `<F11>` `<F5>` | tam ekran / sunum |
| `<C-m>` | durum çubuğunu gizle |
| `o` | dosya aç, `R` yeniden yükle |
| `q` | bakılan belgeyi kapat (`Ctrl+W` de); sonuncusu kapanınca boş ekran |
| `<C-e>` | kapatılan belgeyi geri aç (Ctrl+E): kaldığı sayfa, zoom ve listedeki yeriyle; son 3 (1-10 ayarlanır) |
| `Q` | uygulamadan çık (Shift+q) - belgeler ve konumlar kaydedilir |
| `:` | komut satırı |

Fare: tekerlek kaydırır, `Ctrl`+tekerlek imlecin altındaki yeri sabit tutarak
yakınlaştırır, sürükleme sayfayı taşır.

## Komutlar

`:open <yol>` `:quit` `:reload` `:goto <n>` `:zoom <yüzde>` `:rotate`
`:set <anahtar> <değer>` `:map <tuş> <komut>` `:unmap <tuş>`
`:bmark <ad>` `:blist` `:bdelete <ad>` `:nohl` `:toc` `:info`
`:export <yol.png>` `:lang <en|tr|de>` `:rc` (yapılandırma dosyasının yolu)
`:eylemler` `:help`

Kısaltmalar: `:q` `:o` `:e` `:r` `:bm` `:nohl`.

İç komut adları da doğrudan yazılabilir: `:sonraki-sayfa`.

## Eylem paleti (`<C-k>`)

Tuş değiştirmek için dosya bulup elle düzenlemek gerekmiyor. `<C-k>` bütün iç
komutları, ne işe yaradıklarını ve o anki tuşlarını tek listede açar:

```
> gece
[ yakınlaştırma ve düzen ]
  ters-renk    gece modu: renkleri ters çevir              <C-r>
```

Yazdıkça süzülür (ad, açıklama ya da tuş üzerinden), `<Down>`/`<Up>` gezer,
`Enter` komutu çalıştırır. Seçili komutun üzerinde yine `<C-k>` sağ altta
eylemleri açar:

| | |
|---|---|
| `çalıştır` | komutu çalıştır |
| `tuş ata` | bir tuş bileşkesine bas, `Enter` ile onayla |
| `tuşu kaldır` | birden çok tuş varsa hangisi diye sorar |
| `varsayılana dön` | komutun varsayılan tuşlarını geri getirir |

Onay ekranı ne olacağını basmadan önce söyler: tuş başka bir komuttaysa kimden
alınacağını, sayı tuşu gibi çalışmayacak bir şey seçtiysen nedenini yazar.
`Esc` vazgeçer.

Atama **kalıcı**: `%APPDATA%\rubric\rubricrc` dosyasının sonundaki işaretli
bloğa yazılır. Elle yazdığın satırlara dokunulmaz, varsayılanına dönen tuş
blokta yer tutmaz. Yani palet ile dosya aynı şeyi söyler, biri ötekini ezmez.

## Belge listesi ve oturum

Açtığın belgeler açılış sırasıyla bir listede durur: `Ctrl+Right` sonraki
(daha yeni), `Ctrl+Left` önceki (daha eski), uçlarda başa döner. `B` listeyi
açar (`Enter` git, `x` kapat), `q` (ya da `Ctrl+W`) bakılan belgeyi kapatır;
uygulamadan çıkmak `Q`. Yanlışlıkla kapattığını `Ctrl+E` geri açar
(son 3 tane, en yenisi önce; uygulamayı kapatıp açsan da). Kaç tane
olacağını `Ctrl+K` > ayarlar > `geri-acma-siniri` listesinden 1-10 arası
seçersin; seçim rubricrc'ye `set kapanan-belgeler` olarak yazılır.
Dosya penceresinde birden çok dosya seçilebilir. Durum çubuğunda `[2/3]`.

Uygulamayı kapatıp açınca liste ve son baktığın belge, kaldığın sayfayla geri
gelir (`set oturum false` kapatır). zathura'daki gibi bellekte yalnızca bakılan
belge açık; diğerleri yol + kaldığın yer. Liste `son-belgeler` (varsayılan 10,
zathura'nın `show-recent`'i gibi) ile sınırlı: dolunca en uzun süredir
bakmadığın belge çıkar, silinmiş dosyalar açılışta ayıklanır.

## Temalar

`Ctrl+K` > en alttaki `tema` > Enter: dil seçimi gibi bir liste açılır, on tema
her biri kendi renginde, seçili olan `[x]`. `j/k` ile gez, `Enter` uygular ve
rubricrc'ye `set tema <ad>` yazar; palet açık kalır, başka tema için yine Enter.
`:tema` listeyi açar, `:tema neon` doğrudan geçer (her dildeki ad olur:
`:theme ice`). Temalar: `kirmizi-fosfor` (varsayılan), `yesil-fosfor`,
`kehribar`, `buz`, `neon`, `kutup-gecesi`, `toprak`, `murekkep`, `kagit`,
`gun-isigi`. rubricrc'de elle yazılan tek bir renk (`set vurgu #...`), satır
sırasından bağımsız olarak her temanın üstünde kalır.

## Dil / Language / Sprache

Arayüz İngilizce (varsayılan), Türkçe ve Almanca. Değiştirmek için `<C-k>` >
`dil` > Enter: English / Türkçe / Deutsch listesinden seçilir. `:lang` da aynı
listeyi açar, `:lang tr` doğrudan geçer. Seçim rubricrc'ye `set dil tr` olarak
kalıcı yazılır. Tuş kartı da aynı dili konuşur: `uv run tus-karti.py --dil de`.

The interface speaks English (default), Turkish and German: `<C-k>` >
`language` > Enter opens a picker, `:lang` does the same, `:lang de` switches
directly. Command names are translated too (`scroll-down` / `aşağı` /
`runter`) and a name from any language works everywhere: `:next-page`,
`map x nächste-seite` in rubricrc. The palette always writes the internal id
to rubricrc so switching languages never breaks the file. Setting names
(`set ters-renk`) are not translated.

Palet aksansız yazılanı da bulur (`sigdir` -> "sığdır"). Yazı tipi yoksa
Consolas / Cascadia Mono / DejaVu Sans Mono / Courier New'den ilk bulunana
düşülür; hepsi Türkçe ve Almanca harflerin tamamını taşır.

## Yapılandırma

`rubricrc.ornek` dosyasını `%APPDATA%\rubric\rubricrc` yoluna kopyala. İçinde her
ayarın ne işe yaradığı ve bağlanabilecek bütün iç komutların listesi var.
Çalışırken denemek için `:set`, kalıcı yapmak için dosyaya yaz.

Durum çubuğunun metni de ayar:

```
set durum-bicimi  $ {ad} :: {sayfa}/{toplam} [{yuzde}%] z{zoom}%{ters}{arama}
```

Bozuk bir satır yalnızca kendini düşürür; uygulama açılır, hata durum
çubuğunda görünür.

## Nasıl çalışıyor

- **Render**: PyMuPDF sayfayı PPM'e verir, tkinter `PhotoImage` onu doğrudan
  okur - Pillow'a gerek yok.
- **Kaydırma**: bütün sayfalar tek bir uzun tuvale dizilir, ama yalnızca
  görüntüye girenler işlenir; çıkanlar tuvalden düşürülür. 1612 sayfalık bir
  kitap 0.6 sn'de açılıyor, bellekte hep 12 sayfa duruyor.
- **Konum**: mutlak piksel yerine (sayfa, sayfa içindeki oran) ikilisi
  saklanır. Bu yüzden yakınlaştırınca, pencereyi boyutlandırınca ya da çift
  sayfaya geçince bakılan yer kaymaz; işaretler ve "kaldığı yerden aç" da
  aynı ikiliyi kullanır.
- **Yakınlaştırma**: tekerlek / tuş olayı yalnızca hedef zoom'u günceller;
  kuyrukta olay kalmayınca birikenler tek çizimde uygulanır ve önce yalnızca
  görünen sayfalar işlenir. Hızlı çevrilen tekerlek böylece geride kalmaz
  (1612 sayfada 6 tık: 1.2 sn -> 70 ms).
- **Arama** imlecin olduğu sayfadan başlar, başa sarar ve 6 sayfalık partiler
  hâlinde arka planda yürür. İlk eşleşme ~170 ms'de bulunur, geri kalanı
  dolarken arayüz çalışır. (Tek seferde taramak 1612 sayfada 20 sn donduruyordu.)

## Veriler nerede

| | |
|---|---|
| `%APPDATA%\rubric\rubricrc` | yapılandırma (elle ya da eylem paletinden) |
| `%LOCALAPPDATA%\rubric\durum.json` | dosya başına son okunan yer, işaretler, yer imleri ve vurgular |

`durum.json` açılan belgelerin tam yolunu ve vurgulanan metni de tutar; okuma
geçmişini silmek için bu dosyayı sil. rubric internete hiç bağlanmaz, belgedeki
bağlantıları ve gömülü betikleri çalıştırmaz. Vurgular asıl PDF'e yazılmaz;
yalnızca `:vurgulari-aktar` ayrı bir kopya üretir.

## Testler

`testler\` altındaki betikler arayüzü `mainloop` çağırmadan kurar ve komutları
doğrudan sürer. Geçici bir veri / ayar dizini ve kendi ürettikleri bir deneme
PDF'i kullanırlar; gerçek `rubricrc` ve `durum.json`'a dokunmazlar.

```powershell
uv run testler\duman.py        # bütün komutları sırayla sürer, hata sayar
uv run testler\palet.py        # eylem paleti: gezinme, tuş atama, rubricrc
uv run testler\belgeler.py     # belge listesi, oturum, kapananı geri açma
uv run testler\vurgu.py        # metin vurguları, kalıcılık, aktarma
uv run testler\rc.py           # rubricrc okuyucusu ve rubricrc.ornek
uv run testler\sayfa_git.py    # 42 Enter
uv run testler\zoom.py         # yakınlaştırma: olay birleştirme, imleç çapası, süre
uv run testler\icindekiler.py  # panel: doğru başlıktan açılma, oklar, hatırlama
uv run testler\cerceve.py      # pencere çerçevesi ve üst bar (ekrandan okur)
uv run testler\stres.py        # 1612 sayfada açılış / kaydırma ölçümü
uv run testler\arama.py        # parçalı aramanın arayüzü dondurmadığını ölçer
```

Gerçek bir kitapta ölçmek için `$env:RUBRIC_TEST_PDF = "<yol.pdf>"`.

`testler\fare.py` ayrıdır: işletim sistemine gerçek fare ve klavye girdisi
verir, ~30 sn boyunca imleci ve klavyeyi ele geçirir. Çalışırken bilgisayara
dokunma.

## Lisans

[GNU AGPL-3.0](LICENSE) ya da sonraki bir sürümü. rubric, yine AGPL-3.0
lisanslı [PyMuPDF](https://github.com/pymupdf/PyMuPDF) üzerine kurulu.
Değiştirilmiş bir sürümünü (exe dahil) dağıtan, kaynak kodunu da aynı
lisansla vermek zorunda.
