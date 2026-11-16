"""AI second opinion for an uncertain leaf photo (Gemini vision is faked)."""
import io
import json

from PIL import Image

DEFAULT_REPLY = "Remove the spotted lower leaves and spray mancozeb as per the label [1]."


def _predict(client, headers):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 160, 40)).save(buf, format="PNG")
    r = client.post("/api/disease/predict", headers=headers, files={"image": ("leaf.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_second_opinion_describes_photo_and_is_labelled(client, farmer, services):
    pid = _predict(client, farmer["headers"])
    services.llm.reply = json.dumps({"is_plant": True, "crop": "Grape", "likely_problem": "Black rot",
                                     "other_possibilities": ["Downy mildew"], "symptoms_seen": "Brown spots with dark edges.",
                                     "what_to_do": "Remove infected leaves.", "prevention": "Prune for airflow.",
                                     "confidence": "medium"})
    try:
        r = client.post(f"/api/disease/predictions/{pid}/second-opinion", headers=farmer["headers"],
                        data={"language_code": "en"})
    finally:
        services.llm.reply = DEFAULT_REPLY
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["crop"] == "Grape" and data["likely_problem"] == "Black rot"
    assert data["other_possibilities"] == "Downy mildew"
    assert "not a verified diagnosis" in data["summary_english"]


def test_second_opinion_only_for_own_prediction(client, farmer, admin, services):
    pid = _predict(client, farmer["headers"])
    r = client.post(f"/api/disease/predictions/{pid}/second-opinion", headers=admin["headers"])
    assert r.status_code == 404
