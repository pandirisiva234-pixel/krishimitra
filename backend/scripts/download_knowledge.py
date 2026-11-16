"""Download a starter set of official agricultural PDFs into knowledge_base/documents/.

All sources are Government of India / ICAR / international research institutes.
Each PDF gets a <name>.url file with its source link, which ingest_documents.py stores,
so answers can cite the original document.

    cd backend
    python -m scripts.download_knowledge      # download (skips files already present)
    python -m scripts.ingest_documents        # then index them into ChromaDB

Stop uvicorn while indexing (two programs writing ChromaDB at once can corrupt it).
"""
import ssl
import sys
import time

import httpx

from app.core.config import PROJECT_ROOT

DEST = PROJECT_ROOT / "knowledge_base" / "documents"

# (file name, source URL). File names become document titles (underscores -> spaces).
SOURCES = [
    # Chilli
    ("NIPHM_AESA_IPM_Package_Chilli_Capsicum.pdf",
     "https://niphm.gov.in/IPMPackages/Chilli.pdf"),
    ("ICAR_IISR_Good_Agricultural_Practices_Chilli.pdf",
     "https://spices.icar.gov.in/sites/default/files/Extension%20Pamphlets/GAP-Chillli-1.pdf"),
    ("PPQS_Thrips_parvispinus_Chilli_Monitoring_and_Management.pdf",
     "https://ppqs.gov.in/sites/default/files/south_east_asian_thrips_thrips_parvispinus-monitoring_and_management.pdf"),
    # Tomato
    ("NIPHM_AESA_IPM_Package_Tomato.pdf",
     "https://www.niphm.gov.in/IPMPackages/Tomato.pdf"),
    # Rice / paddy
    ("NIPHM_IPM_Package_Rice.pdf",
     "https://www.niphm.gov.in/IPMPackages/Rice.pdf"),
    ("ICAR_CRRI_Package_of_Practices_Direct_Seeded_Rice.pdf",
     "https://icar-crri.in/wp-content/uploads/2025/12/CRRI_Technology-Bulletin_No-250.pdf"),
    # Cotton
    ("NIPHM_IPM_Package_Cotton.pdf",
     "https://niphm.gov.in/IPMPackages/Cotton.pdf"),
    ("PPQS_IPM_Management_of_Whitefly_in_Cotton.pdf",
     "https://ppqs.gov.in/sites/default/files/pop_for_management_of_white_fly_in_cotton.pdf"),
    # Maize (added Nov 2026: farmers' questions about fall armyworm had no source document)
    ("NIPHM_IPM_Package_Maize.pdf",
     "https://www.niphm.gov.in/IPMPackages/Maize.pdf"),
    ("PPQS_Advisory_Fall_Armyworm_Maize.pdf",
     "https://ppqs.gov.in/sites/default/files/faw_advisory.pdf"),
    # Groundnut
    ("NIPHM_IPM_Package_Groundnut.pdf",
     "https://niphm.gov.in/IPMPackages/Groundnut.pdf"),
    ("ICAR_DGR_Technologies_to_Enhance_Groundnut_Productivity.pdf",
     "https://krishi.icar.gov.in/jspui/bitstream/123456789/4515/1/Technologies%20to%20Enhance%20Groundnut%20Productivity%20-%20Technical%20Bulletin-english.pdf"),
    ("ICRISAT_Improved_Cultivation_Practices_for_Groundnut.pdf",
     "http://oar.icrisat.org/400/1/CO_200705.pdf"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KrishiMitra-academic-project"}


def ssl_context():
    """Use the Windows certificate store when available (fixes many government-site certificate errors)."""
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    ok, skipped, failed = [], [], []
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=120, verify=ssl_context()) as client:
        for name, url in SOURCES:
            target = DEST / name
            if target.exists() and target.stat().st_size > 1000:
                skipped.append(name)
                print(f"skip      {name} (already downloaded)")
                continue
            try:
                print(f"download  {name} ...", end=" ", flush=True)
                resp = client.get(url)
                resp.raise_for_status()
                if not resp.content.startswith(b"%PDF"):
                    raise ValueError("server did not return a PDF (the link may have moved)")
                target.write_bytes(resp.content)
                target.with_suffix(".url").write_text(url, encoding="utf-8")
                ok.append(name)
                print(f"ok ({len(resp.content) / 1e6:.1f} MB)")
            except Exception as exc:  # noqa: BLE001 - report and continue with the next file
                failed.append((name, url, str(exc)[:150]))
                print(f"FAILED: {exc}")
            time.sleep(1)  # be polite to government servers

    print(f"\nDownloaded {len(ok)}, already present {len(skipped)}, failed {len(failed)}")
    if failed:
        print("\nOpen these links in your browser, save the PDF into knowledge_base\\documents\\ with the name shown:")
        for name, url, err in failed:
            print(f"  {name}\n    {url}\n    reason: {err}")
    print("\nNext: stop uvicorn, then run   python -m scripts.ingest_documents")
    sys.exit(0)


if __name__ == "__main__":
    main()
