#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_sailing.py  -  End-to-End Cognee-Lauf fuer den Sailing-Agent-PoC.

Was das Skript tut (= Schritte 1/3/4/5 des Schlachtplans in Code):
  1. Frischer State (prune)                     -> reproduzierbar
  2. add(documents/)                            -> Ingestion + Chunking
  3. cognify(ontology_config=sailing.owl)       -> Graph-Extraktion GEGEN die Ontologie
  4. visualize_graph()                          -> interaktive graph.html
  5. search(...) fuer die echten Beispielfragen -> zeigt, dass der Graph "denkt"

Aufruf:
    cp .env.template .env      # Endpoint-Werte eintragen
    python scripts/run_sailing.py

Nur den Dokumenten-Ordner swappen:
    documents/ leeren, eigene .md/.txt/.pdf reinlegen, erneut ausfuehren.
    (PDF-Support: pip install 'cognee[docs]' falls noetig.)
"""
import os, sys, asyncio, pathlib
from dotenv import load_dotenv

HERE = pathlib.Path(__file__).resolve().parent   # knowledgegraph/
ROOT = HERE.parent                               # sailing-knowledge-agent/
load_dotenv(ROOT / ".env")

import cognee
from cognee.api.v1.search import SearchType
from cognee.modules.ontology.ontology_config import Config
from cognee.modules.ontology.rdf_xml.RDFLibOntologyResolver import RDFLibOntologyResolver

DOCS = HERE / "source"
ONTOLOGY = HERE / "ontology.owl"
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

# Beispielfragen (echte Chat-Fragen) + eine Register/Praxis-Probe.
QUESTIONS = [
    "Why does Peter Burling win so consistently in the 49er?",
    "Comparing Matt Wearn and Philipp Buhl in the ILCA 7 - what factors explain differences in results?",
    "What is the connection between the favoured side and a persistent wind shift?",
    "In practical coaching terms, what does a gybe cost and how do coaches talk about it?",
]

def banner(msg):
    print("\n" + "=" * 72 + f"\n  {msg}\n" + "=" * 72, flush=True)

async def main():
    if not os.getenv("LLM_ENDPOINT") or "DEIN-ENDPOINT" in os.getenv("LLM_ENDPOINT", ""):
        sys.exit("FEHLER: .env nicht konfiguriert - LLM_ENDPOINT/LLM_MODEL/LLM_API_KEY setzen.")

    banner("Schritt 1: Frischer State (prune)")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    print("State zurueckgesetzt.")

    banner("Schritt 2: Ingestion - Dokumente laden")
    files = sorted([str(p) for p in DOCS.glob("**/*") if p.suffix.lower() in {".md", ".txt", ".pdf"}])
    if not files:
        sys.exit(f"Keine Dokumente in {DOCS} gefunden.")
    for f in files:
        print("  +", pathlib.Path(f).name)
    await cognee.add(files)
    print(f"{len(files)} Dokument(e) ingested.")

    banner("Schritt 3: Cognify - Graph GEGEN die Segel-Ontologie extrahieren")
    ontology_config: Config = {
        "ontology_config": {
            "ontology_resolver": RDFLibOntologyResolver(ontology_file=str(ONTOLOGY))
            # "ontology_mode": "strict"  # -> ungegroundete Knoten droppen (erst nach Review!)
        }
    }
    await cognee.cognify(config=ontology_config)
    print("Graph gebaut. Kanten sind gegen die Ontologie gegroundet (ontology_valid=True wo gematcht).")

    banner("Schritt 4: Visualisierung -> output/graph.html")
    html_path = str(OUT / "graph.html")
    await cognee.visualize_graph(destination_file_path=html_path)
    print("Interaktiver Graph:", html_path)

    banner("Schritt 5: Die echten Beispielfragen gegen den Graphen")
    for q in QUESTIONS:
        print("\n--- FRAGE:", q)
        try:
            res = await cognee.search(query_type=SearchType.GRAPH_COMPLETION, query_text=q)
            for r in res:
                print(r if isinstance(r, str) else getattr(r, "text", r))
        except Exception as e:
            print("  [Fehler bei dieser Frage]:", e)

    banner("Fertig. Graph + Antworten liegen in output/.")

if __name__ == "__main__":
    asyncio.run(main())
