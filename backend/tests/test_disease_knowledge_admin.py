"""Disease detection (Module 4), knowledge base (Module 3) and admin (Module 7)."""
from tests.conftest import TELUGU_Q, make_jpeg, register


# ------------------------------------------------------------------ disease
def test_predict_runs_real_onnx_inference(client, farmer):
    resp = client.post("/api/disease/predict", headers=farmer["headers"],
                       files={"image": ("leaf.jpg", make_jpeg((220, 20, 20)), "image/jpeg")})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["predicted_label"] == "Tomato___Early_blight"  # red image -> class 0 in the tiny model
    assert len(data["top_predictions"]) == 3
    assert abs(sum(p["confidence"] for p in data["top_predictions"]) - 1) < 1e-3
    assert data["disease"]["disease_name"] == "Early blight"  # joined with the curated disease table
    assert data["model_version"] == "test-1"
    img = client.get(data["image_url"], headers=farmer["headers"])
    assert img.status_code == 200


def test_low_confidence_is_marked_uncertain(client, farmer):
    grey = make_jpeg((124, 116, 104), noise=False)  # ImageNet mean colour -> all logits 0 -> 1/3 each
    data = client.post("/api/disease/predict", headers=farmer["headers"],
                       files={"image": ("grey.jpg", grey, "image/jpeg")}).json()
    assert data["is_uncertain"] is True and "not confident" in data["message"]
    assert data["is_blurry"] is True  # flat image has no edges


def test_history_and_privacy(client, farmer):
    client.post("/api/disease/predict", headers=farmer["headers"],
                files={"image": ("leaf.jpg", make_jpeg((20, 200, 20)), "image/jpeg")})
    history = client.get("/api/disease/history", headers=farmer["headers"]).json()
    assert len(history) == 1 and history[0]["predicted_label"] == "Tomato___healthy"
    other = register(client, phone="9123456780")
    h2 = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get("/api/disease/history", headers=h2).json() == []
    assert client.get(history[0]["image_url"], headers=h2).status_code == 404


def test_rejects_non_images(client, farmer):
    resp = client.post("/api/disease/predict", headers=farmer["headers"],
                       files={"image": ("leaf.jpg", b"%PDF-1.4 not an image", "image/jpeg")})
    assert resp.status_code == 400
    big = b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024)
    resp = client.post("/api/disease/predict", headers=farmer["headers"], files={"image": ("big.jpg", big, "image/jpeg")})
    assert resp.status_code == 400 and "too large" in resp.json()["error"]["message"]


def test_disease_library(client, farmer):
    classes = client.get("/api/disease/classes", headers=farmer["headers"]).json()
    assert len(classes) == 38
    assert all(c["treatment"] and c["prevention"] for c in classes)


# ------------------------------------------------------------ knowledge base
def test_upload_index_search_delete(client, admin, farmer, knowledge, services):
    docs = client.get("/api/knowledge/documents", headers=farmer["headers"]).json()
    assert docs[0]["status"] == "indexed" and docs[0]["num_chunks"] >= 1
    found = client.post("/api/knowledge/search", headers=farmer["headers"],
                        json={"query": "paddy standing water tillering", "language_code": "en"}).json()
    assert found["results"] and "standing water" in found["results"][0]["snippet"]
    before = services.vector_store.count()
    assert client.delete(f"/api/knowledge/documents/{knowledge['id']}", headers=admin["headers"]).status_code == 200
    assert services.vector_store.count() < before


def _minimal_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_pdf_upload_keeps_page_numbers(client, admin, farmer, services):
    pdf = _minimal_pdf("Groundnut needs gypsum at flowering stage for good pod filling and calcium supply.")
    doc = client.post("/api/knowledge/upload", headers=admin["headers"], data={"title": "Groundnut notes"},
                      files={"file": ("groundnut.pdf", pdf, "application/pdf")}).json()
    listed = {d["id"]: d for d in client.get("/api/knowledge/documents", headers=admin["headers"]).json()}
    assert listed[doc["id"]]["status"] == "indexed", listed[doc["id"]]
    hits = client.post("/api/knowledge/search", headers=farmer["headers"],
                       json={"query": "groundnut gypsum flowering", "language_code": "en"}).json()["results"]
    assert hits[0]["page"] == 1 and hits[0]["title"] == "Groundnut notes"
    services.vector_store.delete_document(doc["id"])


def test_only_admin_can_upload_or_delete(client, farmer):
    resp = client.post("/api/knowledge/upload", headers=farmer["headers"], data={"title": "x doc"},
                       files={"file": ("a.txt", b"hello world", "text/plain")})
    assert resp.status_code == 403
    assert client.delete("/api/knowledge/documents/1", headers=farmer["headers"]).status_code == 403


# --------------------------------------------------------------------- admin
def test_farmer_cannot_open_admin_routes(client, farmer):
    for path in ("/api/admin/dashboard", "/api/admin/users", "/api/admin/statistics", "/api/admin/system"):
        assert client.get(path, headers=farmer["headers"]).status_code == 403


def test_admin_dashboard_and_statistics_reflect_real_data(client, admin, farmer, knowledge):
    client.post("/api/assistant/query", headers=farmer["headers"], json={"text": "tomato leaf spots", "language_code": "en"})
    client.post("/api/assistant/query", headers=farmer["headers"], json={"text": TELUGU_Q})
    client.post("/api/disease/predict", headers=farmer["headers"],
                files={"image": ("leaf.jpg", make_jpeg((220, 20, 20)), "image/jpeg")})
    dash = client.get("/api/admin/dashboard", headers=admin["headers"]).json()
    assert dash["total_farmers"] == 1 and dash["total_admins"] == 1
    assert dash["total_queries"] == 2 and dash["queries_today"] == 2
    assert dash["active_users_7d"] == 1 and dash["total_disease_scans"] == 1 and dash["total_documents"] == 1
    stats = client.get("/api/admin/statistics", headers=admin["headers"]).json()
    assert {i["label"] for i in stats["language_usage"]} == {"English", "Telugu"}
    assert {i["label"] for i in stats["intent_distribution"]} == {"pest_disease"}
    assert stats["disease_distribution"][0] == {"label": "Early blight (Tomato)", "count": 1}
    assert sum(d["count"] for d in stats["queries_per_day"]) == 2
    assert stats["grounded_answer_pct"] == 100.0
    farmer_dash = client.get("/api/dashboard/summary", headers=farmer["headers"]).json()
    assert farmer_dash["total_queries"] == 2 and farmer_dash["total_disease_scans"] == 1
    # chart data
    assert len(farmer_dash["activity_14d"]) == 14 and farmer_dash["activity_14d"][-1]["count"] == 2
    assert sum(d["count"] for d in farmer_dash["activity_14d"]) == 2
    assert farmer_dash["topics"] == [{"label": "pest_disease", "count": 2}]
    assert farmer_dash["scan_outcomes"] == [{"label": "disease", "count": 1}]
    assert len(stats["registrations_per_day"]) == 30 and stats["registrations_per_day"][-1]["count"] == 1
    assert len(stats["response_seconds_per_day"]) == 1 and stats["response_seconds_per_day"][0]["value"] >= 0
    assert stats["scan_outcomes"] == [{"label": "disease", "count": 1}]
    assert stats["feedback"] == []


def test_user_management(client, admin, farmer):
    listing = client.get("/api/admin/users?search=Ravi", headers=admin["headers"]).json()
    assert listing["total"] == 1 and listing["items"][0]["phone"] == "9876543210"
    uid = listing["items"][0]["id"]
    promoted = client.patch(f"/api/admin/users/{uid}", headers=admin["headers"], json={"role": "admin"}).json()
    assert promoted["role"] == "admin"
    me = client.patch(f"/api/admin/users/{admin['id']}", headers=admin["headers"], json={"is_active": False})
    assert me.status_code == 400  # cannot lock yourself out


def test_system_status(client, admin):
    status = client.get("/api/admin/system", headers=admin["headers"]).json()
    assert status["database"] == "ok" and status["vector_store"] == "ok"
    assert status["disease_model_available"] is True and status["openweather_configured"] is True


def test_fill_days_adds_empty_days():
    from datetime import date

    from app.api.routes.dashboard import fill_days
    out = fill_days([(date(2026, 11, 20), 3), ("2026-11-22", 1)], 4, today=date(2026, 11, 22))
    assert out == [{"label": "2026-11-19", "count": 0}, {"label": "2026-11-20", "count": 3},
                   {"label": "2026-11-21", "count": 0}, {"label": "2026-11-22", "count": 1}]


def test_feedback_chart_counts_votes(client, admin, farmer, knowledge):
    r = client.post("/api/assistant/query", headers=farmer["headers"], json={"text": "tomato leaf spots", "language_code": "en"})
    client.post("/api/feedback", headers=farmer["headers"],
                json={"response_id": r.json()["response_id"], "is_helpful": True})
    stats = client.get("/api/admin/statistics?days=7", headers=admin["headers"]).json()
    assert stats["feedback"] == [{"label": "helpful", "count": 1}]
    assert len(stats["registrations_per_day"]) == 7
