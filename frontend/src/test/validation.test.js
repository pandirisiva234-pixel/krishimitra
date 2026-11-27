import { describe, expect, it } from "vitest";
import { errorMessage } from "../api/client";
import { intentLabel, pct, prettyLabel } from "../utils/format";
import { normalisePhone, validatePassword, validatePhone, validateRegistration } from "../utils/validation";

describe("phone validation", () => {
  it("accepts Indian mobile numbers in common formats", () => {
    expect(validatePhone("9876543210")).toBeNull();
    expect(validatePhone("+91 98765 43210")).toBeNull();
    expect(normalisePhone("+91-98765-43210")).toBe("9876543210");
  });
  it("rejects short numbers and landline-style starts", () => {
    expect(validatePhone("12345")).toBeTruthy();
    expect(validatePhone("1234567890")).toBeTruthy();
  });
});

describe("password and registration", () => {
  it("requires length, a letter and a digit", () => {
    expect(validatePassword("short1")).toBeTruthy();
    expect(validatePassword("onlyletters")).toBeTruthy();
    expect(validatePassword("Farmer123")).toBeNull();
  });
  it("reports every invalid field", () => {
    const errors = validateRegistration({ full_name: "", phone: "1", email: "bad", password: "x", confirm: "y" });
    expect(Object.keys(errors).sort()).toEqual(["confirm", "email", "full_name", "password", "phone"]);
  });
  it("passes a valid form", () => {
    expect(
      validateRegistration({ full_name: "Ravi", phone: "9876543210", email: "", password: "Farmer123", confirm: "Farmer123" }),
    ).toEqual({});
  });
});

describe("formatting", () => {
  it("prettifies PlantVillage labels", () => {
    expect(prettyLabel("Tomato___Early_blight")).toBe("Tomato · Early blight");
    expect(prettyLabel("Pepper,_bell___healthy")).toBe("Pepper, bell · healthy");
  });
  it("labels intents and percentages", () => {
    expect(intentLabel("pest_disease")).toBe("Pests & diseases");
    expect(pct(0.876)).toBe("88%");
    expect(pct(null)).toBe("—");
  });
});

describe("API error messages", () => {
  it("uses the backend's error message", () => {
    const err = { response: { status: 409, data: { error: { code: "conflict", message: "Already registered" } } } };
    expect(errorMessage(err)).toBe("Already registered");
  });
  it("lists validation details", () => {
    const err = { response: { status: 422, data: { error: { message: "Invalid input", details: [{ field: "phone", message: "bad" }] } } } };
    expect(errorMessage(err)).toBe("phone: bad");
  });
  it("explains network failures", () => {
    expect(errorMessage({ message: "Network Error" })).toMatch(/Cannot reach the server/);
  });
});

import { warnLabel } from "../pages/VoiceAssistant";
import { translate } from "../i18n";

describe("warnLabel", () => {
  it("names why an answer is not from the documents", () => {
    const label = (en) => translate(warnLabel({ answer_english: en }), null, "en");
    expect(label("I am KrishiMitra, a farming assistant. I can...")).toBe("Outside farming");
    expect(label("Feed well.\n\nThis is general advice, not from KrishiMitra's verified documents."))
      .toBe("General advice, not from verified documents");
    expect(label("I could not find information about this in the KrishiMitra knowledge base"))
      .toBe("Not in the knowledge base");
    expect(translate(warnLabel({ answer_english: "I am KrishiMitra, a farming assistant." }), null, "te"))
      .toBe("వ్యవసాయానికి సంబంధం లేనిది");
  });
});

import { splitForSpeech } from "../utils/format";

describe("splitForSpeech", () => {
  it("starts with one short sentence and drops citation marks", () => {
    const parts = splitForSpeech("Spots are early blight [1]. Remove leaves [2].\n1. Spray as per label [1, 3].");
    expect(parts[0]).toBe("Spots are early blight.");
    expect(parts.slice(1).join(" ")).toBe("Remove leaves. 1. Spray as per label.");
  });
  it("keeps later pieces under the length limit", () => {
    const long = Array.from({ length: 12 }, (_, i) => `Sentence number ${i} is here.`).join(" ");
    const parts = splitForSpeech(long, 80);
    expect(parts.length).toBeGreaterThan(3);
    expect(parts.every((p) => p.length <= 80)).toBe(true);
  });
  it("handles Telugu full stops and empty text", () => {
    expect(splitForSpeech("ఆకులు తొలగించండి. మందు పిచికారీ చేయండి.")).toHaveLength(2);
    expect(splitForSpeech("")).toEqual([]);
  });
});

import { applyTheme, resolveTheme, savedTheme } from "../context/theme";

describe("theme", () => {
  it("saves the choice and sets data-theme on <html>", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(savedTheme()).toBe("dark");
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(resolveTheme("light")).toBe("light");
  });
});

import { diseaseQuestion } from "../pages/DiseaseDetection";

describe("diseaseQuestion", () => {
  it("builds a clear follow-up question from the detected disease", () => {
    expect(diseaseQuestion({ crop: "Tomato", disease_name: "Early blight" })).toBe(
      "How to control early blight in tomato? What are the symptoms and how to prevent it?",
    );
    expect(diseaseQuestion({ crop: "Corn (maize)", disease_name: "Northern Leaf Blight" })).toBe(
      "How to control northern leaf blight in corn? What are the symptoms and how to prevent it?",
    );
  });
});

import { speechSource } from "../components/ListenLanguage";

describe("speechSource", () => {
  it("uses the stored translation, English, or translates English", () => {
    expect(speechSource("తెలుగు", "English", "te", "te")).toEqual({ text: "తెలుగు", translate: false });
    expect(speechSource("తెలుగు", "English", "te", "en")).toEqual({ text: "English", translate: false });
    expect(speechSource("తెలుగు", "English", "te", "hi")).toEqual({ text: "English", translate: true });
  });
});

import { adviceLines } from "../pages/DiseaseDetection";

describe("adviceLines", () => {
  it("lists heading/text pairs then the safety note, one per line", () => {
    const lines = adviceLines({ description: "Fungal.", symptoms: "Spots.", treatment: "Remove\nleaves.", prevention: "" });
    expect(lines).toEqual(["About", "Fungal.", "Symptoms to confirm", "Spots.", "What to do now", "Remove leaves.", expect.stringContaining("product label")]);
  });
});
