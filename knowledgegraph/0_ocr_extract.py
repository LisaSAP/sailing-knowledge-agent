#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ocr_extract.py - struktur-erhaltende Extraktion mit Docling.
Beweist: page_no + heading bleiben pro Chunk erhalten (Zitier-Anker).

WICHTIG (aus dem Docling-Maintainer-Thread verifiziert):
  Export nach Markdown ist VERLUSTBEHAFTET - page_no/bbox gehen verloren.
  Deshalb: DoclingDocument als JSON speichern (lossless) ODER direkt chunken.
  Wir chunken direkt und schreiben pro Chunk {text, page_no, heading} als JSONL.
"""
import sys, os, json, pathlib

def build_converter(describe_pictures=False):
    """
    Standard-Converter. Mit describe_pictures=True wird pro Bild ein VLM
    (ueber euren Proxy) aufgerufen und eine Text-Beschreibung erzeugt -
    noetig fuer Polardiagramme/Kursskizzen, deren Inhalt in Pixeln steckt.
    """
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    opts = PdfPipelineOptions()
    opts.do_table_structure = True          # Tabellen als Struktur (TableFormer)
    opts.generate_picture_images = True     # Bilder mitfuehren
    if describe_pictures:
        # VLM-Bildbeschreibung ueber OpenAI-kompatiblen Proxy (Vision-Modell).
        from docling.datamodel.pipeline_options import PictureDescriptionApiOptions
        opts.do_picture_description = True
        opts.enable_remote_services = True
        opts.picture_description_options = PictureDescriptionApiOptions(
            url=os.environ["LLM_ENDPOINT"].rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["LLM_API_KEY"]},
            params={"model": os.environ.get("VLM_MODEL", "openai/gemini-2.5-flash")},
            prompt="Describe this figure precisely. If it is a chart or polar "
                   "diagram, state axes, units, and the key values/relationships.",
            timeout=90,
        )
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


def main(pdf_path, out_jsonl, describe_pictures=False):
    from docling.chunking import HybridChunker

    conv = build_converter(describe_pictures)
    doc = conv.convert(source=pdf_path).document
    chunker = HybridChunker()

    # Tabellen separat als strukturierte Daten sichern (SQL-/Analytics-faehig)
    tables = []
    for ti, tbl in enumerate(doc.tables):
        try:
            df = tbl.export_to_dataframe(doc)
            tables.append({"table": ti, "shape": list(df.shape), "markdown": tbl.export_to_markdown(doc)})
        except Exception as e:
            tables.append({"table": ti, "error": str(e)})

    # Bildbeschreibungen (falls VLM aktiv)
    pics = []
    for pi, pic in enumerate(doc.pictures):
        desc = None
        for ann in getattr(pic, "annotations", []) or []:
            if getattr(ann, "text", None): desc = ann.text
        page = pic.prov[0].page_no if pic.prov else None
        pics.append({"picture": pi, "page": page, "description": desc})

    rows = []
    for i, chunk in enumerate(chunker.chunk(dl_doc=doc)):
        pages = sorted({p.page_no for it in chunk.meta.doc_items for p in it.prov if hasattr(p, "page_no")})
        heading = chunk.meta.headings[0] if getattr(chunk.meta, "headings", None) else None
        text = chunker.serialize(chunk)
        rows.append({"chunk": i, "pages": pages, "heading": heading, "text": text})

    with open(out_jsonl, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"CHUNKS: {len(rows)} | TABELLEN: {len(tables)} | BILDER: {len(pics)}")
    for r in rows:
        print(f"  #{r['chunk']:>2}  S.{r['pages']}  [{r['heading']}]  {r['text'][:50].replace(chr(10),' ')!r}")
    for t in tables:
        print(f"  [Tabelle {t['table']}] shape={t.get('shape')}")
    for p in pics:
        print(f"  [Bild {p['picture']}] S.{p['page']} desc={(p['description'] or '(keine - VLM aus)')[:60]!r}")
    return rows, tables, pics

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    HERE = pathlib.Path(__file__).resolve().parent          # knowledgegraph/
    ROOT = HERE.parent                                       # sailing-knowledge-agent/
    load_dotenv(ROOT / ".env")

    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="*",
                    help="PDF file(s) to process (default: all PDFs in knowledgegraph/source/)")
    ap.add_argument("--describe-pictures", action="store_true",
                    help="VLM image description via proxy (for polar diagrams etc.)")
    a = ap.parse_args()

    if a.pdf:
        pdfs = [pathlib.Path(p) for p in a.pdf]
    else:
        pdfs = sorted((HERE / "source").glob("*.pdf"))

    if not pdfs:
        raise SystemExit(f"No PDFs found in {HERE / 'source'}")

    (HERE / "output").mkdir(parents=True, exist_ok=True)

    for pdf in pdfs:
        out = str(HERE / "output" / (pdf.stem + ".jsonl"))
        print(f"\n{'='*60}\nProcessing: {pdf.name}\n{'='*60}")
        main(str(pdf), out, a.describe_pictures)
