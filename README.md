# Anand Vidhya worksheets

Printable handwriting worksheets for Anand Vidhya, on four lines, a double line or squares
(like a maths square-line notebook, with one letter or number in each square, written across or down the page).

- **My Name**: https://bhaskar0210s.github.io/av/my_name/

Each worksheet is a single static page (`my_name/index.html`). Open it in a browser to edit and print; no build step.

## Numbers the way children write them

The sheets draw 1 without a foot and 4 open at the top, the way children are taught to write them.
These two shapes, and the empty font that lays out the squares, are small fonts kept inside the page.
To change them, edit `tools/make_fonts.py` and run it; it rewrites the font data in `my_name/index.html`:

```sh
pip install fonttools brotli
python3 tools/make_fonts.py
```
