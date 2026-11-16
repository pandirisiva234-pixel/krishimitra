# Where to get agricultural documents

The assistant can only answer what is in these documents. Use official, public sources and record each
source URL when uploading (it is shown to farmers and cited in your report).

Good sources (search the site for the crop name plus "package of practices" or "crop production guide"):

| Source | What to look for |
| --- | --- |
| Your State Agricultural University (e.g. ANGRAU for Andhra Pradesh, PJTSAU for Telangana, TNAU, UAS Bangalore) | Package of practices for paddy, chilli, cotton, groundnut, tomato |
| TNAU Agritech Portal | Crop production, plant protection and nutrient management pages |
| ICAR institutes (e.g. NRRI for rice, CICR for cotton, DGR for groundnut) | Technical bulletins and extension folders |
| Vikaspedia (agriculture section) | Simple-language crop guides |
| Department of Agriculture & Farmers Welfare | Advisories, IPM guidelines |

Tips:
- Prefer text PDFs. Scanned PDFs (images of pages) contain no extractable text; run OCR first.
- 20–40 good documents for your main crops are better than hundreds of loosely related ones.
- Name files clearly (e.g. `ANGRAU_Chilli_Package_of_Practices_2024.pdf`). For bulk import, put them in
  `knowledge_base/documents/`, add `<same name>.url` files containing the source link, and run
  `python -m scripts.ingest_documents` from `backend/`.
- Check the licence/terms of each source and cite it in the report's references.
