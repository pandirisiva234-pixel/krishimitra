"""Identify a farm product or item from a photo (pesticide bottle, fertilizer bag, seed packet, tool...).

Gemini reads the photo, including the printed label, and returns structured facts. Safety rules:
- information comes from what is PRINTED on the label; nothing is invented,
- no doses beyond what the label itself shows; the farmer is always told to follow the label,
- India's pesticide toxicity triangle colour is reported when visible (red = most toxic),
- a photo that is not a farm item, or an unreadable label, is reported honestly.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

CATEGORIES = [
    "insecticide", "fungicide", "herbicide", "bio-pesticide", "fertilizer", "micronutrient",
    "plant growth regulator", "seed", "veterinary medicine", "animal feed", "farm tool or equipment", "other",
]
TOXICITY = {"red": "Extremely toxic", "yellow": "Highly toxic", "blue": "Moderately toxic", "green": "Slightly toxic"}

SYSTEM_PROMPT = f"""You help small farmers in India understand farm products from a photo.
Look at the photo and read any printed label carefully. Reply with ONE JSON object only, with these keys:
  "is_farm_item": true or false (false for people, animals, food, documents or anything not used in farming),
  "category": one of {json.dumps(CATEGORIES)},
  "product_name": brand/product name exactly as printed, or null,
  "active_ingredient": chemical or active ingredient with its % as printed, or null,
  "used_for": one or two simple sentences: what this item is used for,
  "targets": pests, diseases, weeds, crops or animals it is meant for AS PRINTED on the label, or null,
  "how_to_use": general guidance in simple words; quote a dose ONLY if it is clearly printed on the label,
  "safety": the most important safety advice for this item,
  "toxicity_colour": colour of the diamond/triangle toxicity mark if visible: "red", "yellow", "blue", "green", or null,
  "label_readable": true if you could read the label text, else false,
  "confidence": "high", "medium" or "low".
Rules: never invent a product name, ingredient or dose that is not visible; if unsure, use null and set confidence
low; keep every value short and in simple English; no markdown."""

FALLBACK_SAFETY = ("Read the label before use, wear gloves and a mask, keep away from children and food, "
                   "and ask your agriculture officer or veterinary doctor if unsure.")


def _parse(text: str) -> dict:
    text = (text or "").strip()
    match = re.search(r"\{.*\}", text, re.S)  # tolerate ```json fences or extra words
    if not match:
        raise ValueError("no JSON object in the model reply")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("model reply is not an object")
    return data


def normalise(data: dict) -> dict:
    """Clean the model's JSON into the fields the app shows, with safe defaults."""
    def text(key):
        value = data.get(key)
        if value is None or isinstance(value, (dict, list)):
            return None if not isinstance(value, list) else ", ".join(str(v) for v in value) or None
        value = str(value).strip()
        return value or None

    category = (text("category") or "other").lower()
    colour = (text("toxicity_colour") or "").lower() or None
    colour = colour if colour in TOXICITY else None
    confidence = (text("confidence") or "low").lower()
    return {
        "is_farm_item": bool(data.get("is_farm_item", True)),
        "category": category if category in CATEGORIES else "other",
        "product_name": text("product_name"),
        "active_ingredient": text("active_ingredient"),
        "used_for": text("used_for"),
        "targets": text("targets"),
        "how_to_use": text("how_to_use"),
        "safety": text("safety") or FALLBACK_SAFETY,
        "toxicity_colour": colour,
        "toxicity_meaning": TOXICITY.get(colour) if colour else None,
        "label_readable": bool(data.get("label_readable", False)),
        "confidence": confidence if confidence in ("high", "medium", "low") else "low",
    }


async def identify_item(llm, image: bytes, mime: str) -> dict:
    reply = await llm.generate(
        "Identify this farm item and explain it for a farmer.", SYSTEM_PROMPT,
        image=(image, mime), json_output=True,
    )
    try:
        return normalise(_parse(reply))
    except (ValueError, json.JSONDecodeError):
        logger.warning("Could not parse the item reply: %r", reply[:300])
        return normalise({"is_farm_item": True, "category": "other", "label_readable": False, "confidence": "low",
                          "used_for": "I could not identify this item clearly. Please take a closer photo of the label."})


def summary_text(item: dict) -> str:
    """Plain-text explanation (translated and spoken in the farmer's language)."""
    if not item["is_farm_item"]:
        return ("This does not look like a farm product. Please take a clear photo of a pesticide, "
                "fertilizer, seed packet, medicine or farm tool, with the label visible.")
    lines = []
    name = item["product_name"] or "This item"
    lines.append(f"{name} is a {item['category']}.")
    if item["active_ingredient"]:
        lines.append(f"Active ingredient: {item['active_ingredient']}.")
    if item["used_for"]:
        lines.append(item["used_for"])
    if item["targets"]:
        lines.append(f"It is meant for: {item['targets']}.")
    if item["how_to_use"]:
        lines.append(f"How to use: {item['how_to_use']}")
    if item["toxicity_meaning"]:
        lines.append(f"Toxicity mark: {item['toxicity_colour']}, {item['toxicity_meaning'].lower()}.")
    lines.append(f"Safety: {item['safety']}")
    lines.append("Always follow the dose printed on the label and ask your agriculture officer if unsure.")
    return "\n".join(lines)
