# Working with flowchart.tex / flowchart.pdf

## View the PDF

```bash
evince flowchart.pdf          # GNOME viewer
xdg-open flowchart.pdf        # default system viewer
```

---

## Recompile after edits

```bash
pdflatex -interaction=nonstopmode flowchart.tex
```

---

## Convert to other formats

### SVG (best for web / Markdown embed)

**Option A — Inkscape (installed, recommended):**
```bash
inkscape --export-type=svg flowchart.pdf -o flowchart.svg
```

**Option B — pdftocairo (poppler-utils, installed):**
```bash
pdftocairo -svg flowchart.pdf flowchart.svg
```

### PNG (for quick sharing or README embeds)

```bash
# 300 dpi — good for screen
pdftoppm -r 300 -png flowchart.pdf flowchart
# output: flowchart-1.png

# higher dpi for print / presentations
pdftoppm -r 600 -png flowchart.pdf flowchart
```

### PNG via ImageMagick (installed):
```bash
convert -density 300 flowchart.pdf flowchart.png
```

> Note: ImageMagick may require ghostscript policy tweak for PDF input.
> If you see a policy error, run:
> ```bash
> sudo sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' \
>     /etc/ImageMagick-6/policy.xml
> ```

---

## Install pdf2svg (optional, lightest tool)

```bash
sudo apt install pdf2svg
pdf2svg flowchart.pdf flowchart.svg
```
