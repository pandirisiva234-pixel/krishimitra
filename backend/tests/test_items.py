"""Farm item identification (Gemini vision is faked; the photo goes through real upload validation)."""
import io
import json

from PIL import Image

from app.services.vision.item_identifier import normalise, summary_text

DEFAULT_REPLY = "Remove the spotted lower leaves and spray mancozeb as per the label [1]."


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 80, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _post(client, headers, reply, services, lang="en"):
    services.llm.reply = reply
    try:
        return client.post("/api/items/identify", headers=headers, data={"language_code": lang},
                           files={"image": ("bottle.png", _png(), "image/png")})
    finally:
        services.llm.reply = DEFAULT_REPLY


def test_identifies_pesticide_bottle(client, farmer, services):
    reply = json.dumps({
        "is_farm_item": True, "category": "insecticide", "product_name": "Example 5 EC",
        "active_ingredient": "Emamectin benzoate 5% SG", "used_for": "Controls caterpillars on crops.",
        "targets": ["fruit borer", "bollworm"], "how_to_use": "Mix with water as printed on the label.",
        "safety": "Wear gloves and a mask.", "toxicity_colour": "Yellow", "label_readable": True, "confidence": "high",
    })
    r = _post(client, farmer["headers"], reply, services)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["category"] == "insecticide" and data["targets"] == "fruit borer, bollworm"
    assert data["toxicity_colour"] == "yellow" and data["toxicity_meaning"] == "Highly toxic"
    assert "Always follow the dose printed on the label" in data["summary_english"]


def test_answer_is_translated_to_farmer_language(client, farmer, services):
    reply = json.dumps({"is_farm_item": True, "category": "fertilizer", "used_for": "Gives nitrogen to crops."})
    data = _post(client, farmer["headers"], reply, services, lang="te").json()
    assert data["language_code"] == "te" and data["summary"].startswith("<tel_Telu>")


def test_bad_model_reply_is_handled_honestly(client, farmer, services):
    data = _post(client, farmer["headers"], "Sorry, I cannot tell.", services).json()
    assert data["confidence"] == "low" and "closer photo of the label" in data["used_for"]


def test_rejects_non_image_upload(client, farmer):
    r = client.post("/api/items/identify", headers=farmer["headers"],
                    files={"image": ("notes.png", b"not an image at all", "image/png")})
    assert r.status_code in (400, 415, 422)


def test_requires_login(client):
    r = client.post("/api/items/identify", files={"image": ("bottle.png", _png(), "image/png")})
    assert r.status_code == 401


def test_normalise_cleans_unknown_values():
    item = normalise({"is_farm_item": False, "category": "rocket fuel", "toxicity_colour": "purple", "confidence": "?"})
    assert item["category"] == "other" and item["toxicity_colour"] is None and item["confidence"] == "low"
    assert "does not look like a farm product" in summary_text(item)
