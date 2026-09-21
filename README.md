# rubric

A keyboard-driven document reader for Windows in the spirit of zathura, with
vim-style keys. The interface is built on tkinter and pages are rendered by
PyMuPDF (MuPDF).

The name comes from the red ink that medieval scribes used for headings
(Latin *rubrica*), and the default theme is red phosphor.

rubric opens anything MuPDF can open: PDF, EPUB, XPS, CBZ, MOBI and FB2.

## Installation

Requirements: Windows 10 or 11 and [uv](https://docs.astral.sh/uv/). uv
installs Python 3.12 on its own.

```powershell
uv sync
uv run rubric.py <file.pdf>
```

`uv run kisayol.py` creates a **rubric** shortcut with its icon on the desktop.
Double-clicking it opens rubric without a console window, and you can drop a
PDF onto it. `rubric.cmd` is there if you want to associate the `.pdf`
extension with rubric.

In place of the white Windows title bar, rubric draws a top bar that follows
the theme: `$ rubric <file>` and `[-] [+] [x]`. Dragging the bar (or the status
bar at the bottom) moves the window, a double-click maximizes it, and the top
edge of the bar resizes it. `Ctrl-K` > `top-bar` turns the bar on or off, and
the choice is saved to rubricrc. To bring back the native Windows title bar,
use `set windows-basligi true`.

rubric can also be built as a standalone executable with no console window.
It does not need Python installed, and you can drop a PDF onto it:

```powershell
uv run --with pyinstaller exe-yap.py      # -> dist\rubric\rubric.exe
```

The executable runs together with the `_internal` folder next to it. To give it
to someone else, zip the whole `dist\rubric` folder. Startup takes about
0.3 seconds; only the first launch of a freshly built executable takes a few
seconds longer because of the Defender scan.

`uv run tus-karti.py` writes a PDF reference card of the key bindings to the
desktop (`rubric-tuslari.pdf`). The card reads the bindings from the key map in
`rubric.py`, so it always matches the current keys.

## Keys

| | |
|---|---|
| `j` `k` `h` `l` | scroll (arrow keys work too) |
| `<C-d>` `<C-u>` | half a screen |
| `<Space>` `<C-f>` / `<C-b>` | a full screen forward / back |
| `J` `K` | next / previous page |
| `gg` `G` | first / last page; `42G` or `42` Enter goes to page 42 |
| `5j` | every command accepts a count prefix |
| `s` `a` | fit to width / fit page |
| `+` `-` | zoom in / out; `<C-0>` resets to 100% |
| `r` | rotate 90 degrees |
| `<C-r>` | night mode (invert colors) |
| `d` | two-page view |
| `<Tab>` | table of contents (`j/k/Enter/Esc`) |
| `<C-k>` | action palette: commands, their keys, key binding |
| `/` `?` | search forward / backward, `n` `N` to step, `<Esc>` to clear matches |
| `Shift`+drag | highlight text; with the highlighter on (`v`), a plain drag highlights too |
| right click | delete a highlight; `u` undoes the last highlight change |
| `V` | highlight list (`j/k`, `Enter` to jump, `x` to delete) |
| `:export-highlights` | writes a `<name>-highlighted.pdf` copy; the original PDF is never modified |
| `m<letter>` `'<letter>` | set a mark / jump to a mark |
| `<C-o>` `<C-i>` | back / forward in the jump history |
| `<F11>` `<F5>` | fullscreen / presentation |
| `<C-m>` | hide the status bar |
| `o` | open a file, `R` reloads |
| `q` | close the current document (also `Ctrl+W`); closing the last one leaves an empty window |
| `<C-e>` | reopen a closed document at its page, zoom and list position; the last 3 are kept (adjustable from 1 to 10) |
| `Q` | quit (Shift+q); open documents and positions are saved |
| `:` | command line |

Mouse: the wheel scrolls, `Ctrl`+wheel zooms while keeping the point under the
cursor in place, and dragging moves the page.

## Commands

`:open <path>` `:quit` `:reload` `:goto <n>` `:zoom <percent>` `:rotate`
`:set <key> <value>` `:map <key> <command>` `:unmap <key>`
`:bmark <name>` `:blist` `:bdelete <name>` `:nohl` `:toc` `:info`
`:export <path.png>` `:lang <en|tr|de>` `:rc` (path of the configuration file)
`:actions` `:help`

Abbreviations: `:q` `:o` `:e` `:r` `:bm` `:nohl`.

Internal command names can be typed directly as well: `:next-page`.

## Action palette (`<C-k>`)

Changing a key binding does not require finding and editing a file by hand.
`<C-k>` lists every internal command with a short description and its current
keys:

```
> night
[ zoom and layout ]
  invert-colors    night mode: invert colors              <C-r>
```

Typing filters the list by name, description or key. `<Down>`/`<Up>` move
through it and `Enter` runs the command. Pressing `<C-k>` again on the selected
command opens its actions in the lower right corner:

| | |
|---|---|
| `run` | run the command |
| `bind key` | press a key combination, confirm with `Enter` |
| `remove key` | asks which one if the command has several keys |
| `reset to default` | restores the command's default keys |

The confirmation screen tells you what will happen before anything changes. If
the key already belongs to another command, it names that command; if the key
cannot work (a digit, for example), it says why. `Esc` cancels.

Bindings are **persistent**. They are written to a marked block at the end of
`%APPDATA%\rubric\rubricrc`. Lines you wrote yourself are left untouched, and a
key reset to its default takes no space in the block, so the palette and the
file always agree and neither overwrites the other.

## Document list and session

Open documents are kept in a list in the order they were opened.
`Ctrl+Right` goes to the next (newer) one and `Ctrl+Left` to the previous
(older) one, wrapping around at both ends. `B` opens the list (`Enter` to jump,
`x` to close). `q` (or `Ctrl+W`) closes the current document and `Q` quits the
application. `Ctrl+E` reopens a document closed by mistake. The last 3 are
kept, newest first, even across restarts. The number can be set from 1 to 10
under `Ctrl+K` > settings > `reopen-limit`, and the choice is saved to rubricrc
as `set kapanan-belgeler`. The file dialog accepts multiple files. The status
bar shows the position as `[2/3]`.

When rubric starts again, the list comes back and the last document opens at
the page where you left it (`set oturum false` turns this off). As in zathura,
only the current document is held in memory; the others are stored as a path
and a position. The list is limited by `son-belgeler` (10 by default, like
zathura's `show-recent`). When it is full, the document you have not looked at
for the longest time drops out, and deleted files are pruned at startup.

## Themes

`Ctrl+K` > `theme` at the bottom > Enter opens a picker like the language one.
Each of the ten themes is drawn in its own colors and the active one is marked
`[x]`. `j/k` moves, and `Enter` applies the theme and writes `set tema <name>`
to rubricrc. The palette stays open, so you can press Enter on another theme
right away. `:theme` opens the list and `:theme neon` switches directly; a
theme name from any language works (`:tema buz`). Themes: `red-phosphor`
(default), `green-phosphor`, `amber`, `ice`, `neon`, `polar-night`, `earth`,
`ink`, `paper`, `daylight`. A single color set by hand in rubricrc
(`set vurgu #...`) overrides every theme regardless of where the line appears.

## Language

The interface is available in English (default), Turkish and German.
`<C-k>` > `language` > Enter opens a picker with English / Türkçe / Deutsch.
`:lang` opens the same picker and `:lang tr` switches directly. The choice is
saved to rubricrc as `set dil tr`. The key card uses the same languages:
`uv run tus-karti.py --dil de`.

Command names are translated as well (`scroll-down` / `aşağı` / `runter`), and
a name in any language works everywhere: `:next-page`, or
`map x nächste-seite` in rubricrc. The palette always writes the internal
identifier to rubricrc, so switching languages never breaks the file. Setting
names (`set ters-renk`) are not translated.

The palette also matches text typed without diacritics (`sigdir` finds
"sığdır"). If the configured font is missing, rubric falls back to the first
available of Consolas, Cascadia Mono, DejaVu Sans Mono and Courier New, all of
which cover the full Turkish and German alphabets.

## Configuration

Copy `rubricrc.ornek` to `%APPDATA%\rubric\rubricrc`. The file documents every
setting and lists all internal commands that can be bound to keys. Use `:set`
to try a setting while rubric is running, and write it to the file to keep it.

The status bar text is a setting too:

```
set durum-bicimi  $ {ad} :: {sayfa}/{toplam} [{yuzde}%] z{zoom}%{ters}{arama}
```

A malformed line is skipped on its own. rubric still starts, and the error is
shown in the status bar.

## How it works

- **Rendering.** PyMuPDF renders a page to PPM, which tkinter's `PhotoImage`
  reads directly, so Pillow is not needed.
- **Scrolling.** All pages are laid out on one tall canvas, but only the pages
  in view are rendered, and pages that leave the view are dropped from the
  canvas. A 1612-page book opens in 0.6 seconds and keeps 12 pages in memory.
- **Position.** rubric stores the position as a pair of page number and
  relative offset within the page rather than as absolute pixels. Zooming,
  resizing the window or switching to two-page view therefore keeps the same
  spot in view. Marks and session restore use the same pair.
- **Zoom.** A wheel or key event only updates the target zoom level. Once the
  event queue is empty, the accumulated change is applied in a single redraw,
  and the visible pages are rendered first. Fast wheel scrolling does not fall
  behind as a result (six notches on 1612 pages: 1.2 s down to 70 ms).
- **Search** starts at the page under the cursor, wraps around, and runs in the
  background in batches of six pages. The first match appears in about 170 ms
  and the interface stays responsive while the rest are collected. A
  single-pass search froze the interface for 20 seconds on 1612 pages.

## Data locations

| | |
|---|---|
| `%APPDATA%\rubric\rubricrc` | configuration (edited by hand or from the action palette) |
| `%LOCALAPPDATA%\rubric\durum.json` | per-file reading position, marks, bookmarks and highlights |

`durum.json` also contains the full paths of opened documents and the
highlighted text. Delete the file to clear the reading history. rubric never
connects to the internet and does not follow links or run scripts embedded in
documents. Highlights are never written to the original PDF; only
`:export-highlights` produces a separate copy.

## License

[GNU AGPL-3.0](LICENSE) or any later version. rubric is built on
[PyMuPDF](https://github.com/pymupdf/PyMuPDF), which is also licensed under
AGPL-3.0. Anyone who distributes a modified version, including an executable
build, must provide its source code under the same license.
