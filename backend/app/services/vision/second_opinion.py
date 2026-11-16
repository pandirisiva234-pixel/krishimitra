"""AI second opinion for a leaf photo the trained model is unsure about.

The CNN only knows the 38 PlantVillage classes and drops to about 28% accuracy on field photos.
When it is not confident, the farmer can ask Gemini (vision) to describe what it sees and suggest
likely causes. This is clearly labelled as a general AI opinion, not a verified diagnosis.
"""
import json
import re

SYSTEM_PROMPT = """You help small farmers in India. Look at this plant photo.
Reply with ONE JSON object only, with these keys:
  "is_plant": true or false,
  "crop": the crop or plant you think it is, or null,
  "likely_problem": the most likely disease, pest or deficiency, or "Looks healthy", or null if unclear,
  "other_possibilities": up to two other possible causes, or [],
  "symptoms_seen": what you can see on the leaf, in simple words,
  "what_to_do": 2-3 practical steps in simple words; no exact chemical doses or brand names,
  "prevention": one or two prevention tips,
  "confidence": "high", "medium" or "low".
Be honest: if the photo is unclear or could be several things, say so and use "low"."""

NOTE = ("This is a general AI opinion from the photo, not a verified diagnosis. Confirm with your local "
        "agriculture officer or KVK before spraying, and always follow the product label.")


def parse(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    data = json.loads(match.group(0)) if match else {}
    if not isinstance(data, dict):
        data = {}

    def s(key):
        v = data.get(key)
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v if x)
        v = str(v).strip() if v not in (None, "") else None
        return v or None

    confidence = (s("confidence") or "low").lower()
    return {
        "is_plant": bool(data.get("is_plant", bool(data))),
        "crop": s("crop"),
        "likely_problem": s("likely_problem"),
        "other_possibilities": s("other_possibilities"),
        "symptoms_seen": s("symptoms_seen"),
        "what_to_do": s("what_to_do"),
        "prevention": s("prevention"),
        "confidence": confidence if confidence in ("high", "medium", "low") else "low",
    }


def summary_text(op: dict) -> str:
    if not op["is_plant"]:
        return "This photo does not look like a plant. Please take a clear photo of one affected leaf."
    parts = []
    if op["crop"]:
        parts.append(f"Crop: {op['crop']}.")
    if op["likely_problem"]:
        parts.append(f"Most likely: {op['likely_problem']}.")
    if op["other_possibilities"]:
        parts.append(f"Other possibilities: {op['other_possibilities']}.")
    if op["symptoms_seen"]:
        parts.append(f"What I can see: {op['symptoms_seen']}")
    if op["what_to_do"]:
        parts.append(f"What to do: {op['what_to_do']}")
    if op["prevention"]:
        parts.append(f"Prevention: {op['prevention']}")
    parts.append(NOTE)
    return "\n".join(parts)


async def second_opinion(llm, image: bytes, mime: str) -> dict:
    reply = await llm.generate("Look at this plant photo and help the farmer.", SYSTEM_PROMPT,
                               image=(image, mime), json_output=True)
    try:
        return parse(reply)
    except (ValueError, json.JSONDecodeError):
        return parse("{}") | {"is_plant": True, "symptoms_seen": "The photo could not be analysed clearly."}
