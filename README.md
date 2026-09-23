# rubric

A zathura-style document reader for Windows with vim keys. tkinter for the UI,
PyMuPDF for rendering. Opens PDF, EPUB, XPS, CBZ, MOBI and FB2.

Named after *rubrica*, the red ink medieval scribes used for headings. The
default theme is red phosphor.

## Install

Windows 10/11. Paste into PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new terminal (so `uv` is on PATH), then:

```powershell
git clone https://github.com/iamginto/rubric.git
cd rubric
uv sync
uv run rubric.py
```

Skip the first step if you already have [uv](https://docs.astral.sh/uv/).
No git? Download the ZIP from GitHub, extract it and start from `cd`. To open
a file directly: `uv run rubric.py "C:\path\to\book.pdf"`.

- `uv run kisayol.py` puts a desktop shortcut (no console, drop PDFs on it).
- `uv run --with pyinstaller exe-yap.py` builds `dist\rubric\rubric.exe`. Ship the whole folder.
- `uv run tus-karti.py` prints a key cheat sheet PDF to the desktop.
- `uv run birlikte-ac.py` adds rubric to Windows' "Open with" list (`--kaldir` undoes it).

## Keys

| | |
|---|---|
| `j` `k` `h` `l` | scroll |
| `<C-d>` `<C-u>` / `<Space>` `<C-b>` | half / full screen |
| `J` `K` | next / previous page |
| `gg` `G` `42G` | first / last / page 42 |
| `s` `a` | fit width / fit page |
| `+` `-` `<C-0>` | zoom, reset |
| `r` `d` `<C-r>` | rotate, two-page, night mode |
| `<Tab>` | table of contents |
| `/` `?` `n` `N` | search |
| `Shift`+drag, `V`, `u` | highlight, list, undo |
| `i` | margin note (hover the `[n]` to read it) |
| `<Delete>` | delete mode: click a note or highlight to kill it |
| `S` | page organizer: move, delete, rotate, extract pages |
| `X` | redact pen: drag a box or click a word, `Enter` writes the copy |
| `U` `<C-z>` | bring back the last deleted thing |
| `m<x>` `'<x>` | set / jump to mark |
| `M` `b` | add bookmark, bookmarks panel |
| `<C-l>` | show links on the page |
| `<C-p>` `P` | print, print dialog |
| `<A-Right>` `<A-Left>` | send doc to right / left pane |
| `<A-w>` `<A-o>` | switch pane, back to one pane |
| `<C-o>` `<C-i>` | jump history |
| `<C-Left>` `<C-Right>` `B` | switch documents, document list |
| `q` `<C-e>` `Q` | close doc, reopen closed, quit |
| `<F11>` `<F5>` | fullscreen, presentation |
| `<C-k>` | action palette |
| `:` | command line |

Counts work everywhere (`5j`). `Ctrl`+wheel zooms around the cursor.

## Action palette

`<C-k>` lists every command with its keys. Type to filter, `Enter` to run,
`<C-k>` again to bind or unbind a key. Bindings are saved to
`%APPDATA%\rubric\rubricrc` without touching your own lines.

Themes (10) and language (English, Turkish, German) are picked from the
palette too, or with `:theme` and `:lang`.

## PDF tools

None of these touch the original; each writes a new file next to it.

- `S` page organizer: thumbnails, `hjkl` to walk, `HJKL` to carry, `x` delete,
  `r`/`R` rotate, `v` select, `e` extract, `u` undo, `w` write.
- `X` redact pen, or `:redact <word>` for every match. Text is really removed,
  not just covered (`<name>-redacted.pdf`).
- `:merge` appends chosen PDFs, each keeps its own TOC entry.
- `:strip-metadata` drops author, app, dates, XMP and comment authors.
- `:export-highlights` embeds highlights and margin notes as real PDF comments.

## Config

Copy `rubricrc.ornek` to `%APPDATA%\rubric\rubricrc`. Every setting and
command is documented in there. A bad line is skipped, not fatal.

Open documents and positions come back on restart. Reading state lives in
`%LOCALAPPDATA%\rubric\durum.json`; delete it to clear history.


## License

[AGPL-3.0](LICENSE) or later, same as PyMuPDF.
