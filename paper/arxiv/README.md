# Paper: arXiv version

- `jaden.tex`: the source (pdfLaTeX; Japanese text through the `CJKutf8` package).
- `fair_curves.pdf`: the figure, made by `benchmarks/posthoc/figure.py`.
- `jaden.pdf`: the compiled paper, for reading and sending.

## Build

```bash
pdflatex jaden.tex && pdflatex jaden.tex
```

Needs a TeX installation with the CJK packages (TeX Live full, or on Debian/Ubuntu:
`texlive-latex-recommended texlive-latex-extra latex-cjk-japanese latex-cjk-japanese-wadalab`).

## Submitting to arXiv

1. Upload `jaden.tex` and `fair_curves.pdf` (not `jaden.pdf`: arXiv builds the paper from the source
   itself).
2. Processor: pdfLaTeX. Licence: CC BY 4.0 fits the data licences.
3. Suggested category: cs.CL (Computation and Language), cross-listed to cs.IR and cs.LG.
4. arXiv asks first-time submitters for an **endorsement** in most categories unless they are
   endorsed automatically (for example through a recognised academic email address). An endorser is an
   established author in the category; a researcher you contact about the work can be asked.

Every number in the paper comes from a result file in `benchmarks/` (the held-out tests in `heldout/` and
`heldout2/`, the analyses made after them in `posthoc/`).
