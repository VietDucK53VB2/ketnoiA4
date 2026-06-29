# AI Vision report

This folder contains a LaTeX report scaffold based on `Template_BCTT_DATN`, adapted for the AI Vision service.

## Edit these fields first

- `report/settings.tex`
- `\TenSinhVien`
- `\MaSinhVien`
- `\KhoaHoc`
- `\ChuyenNganh`
- `\GiangVienHD`
- `\Nam`

## Compile

Use XeLaTeX:

```bash
xelatex main.tex
xelatex main.tex
```

Or with `latexmk` if installed:

```bash
latexmk -xelatex main.tex
```
