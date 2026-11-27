import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { I18nProvider, translate, translateMessage, useI18n } from "../i18n";
import { STRINGS } from "../i18n/strings";
import UserGuide from "../components/UserGuide";
import { demoVideoFor } from "../components/DemoVideo";

const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

describe("interface translations", () => {
  const en = STRINGS.en;
  for (const [lang, dict] of Object.entries(STRINGS)) {
    it(`${lang} has every key with the same placeholders`, () => {
      expect(Object.keys(dict).sort()).toEqual(Object.keys(en).sort());
      for (const key of Object.keys(en)) expect(placeholders(dict[key]), `${lang} ${key}`).toBe(placeholders(en[key]));
    });
  }

  it("fills placeholders and falls back to English", () => {
    expect(translate("dash.namaste", { name: "Ravi" }, "te")).toBe("నమస్తే, Ravi");
    expect(translate("speech.part", { i: 2, n: 5 }, "en")).toBe("Part 2 of 5");
    expect(translate("no.such.key", null, "hi")).toBe("no.such.key");
  });

  it("translates fixed English messages from form checks", () => {
    expect(translateMessage("Passwords do not match", "hi")).toBe("पासवर्ड मेल नहीं खाते");
    expect(translateMessage("Some server message", "hi")).toBe("Some server message");
  });
});

function Probe() {
  const { t, lang, setLang } = useI18n();
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span>{t("nav.weather")}</span>
      <button onClick={() => setLang("kn")}>switch</button>
    </div>
  );
}

describe("language switching", () => {
  beforeEach(() => localStorage.clear());

  it("changes every label at once and remembers the choice", async () => {
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByText("Weather")).toBeInTheDocument();
    await userEvent.click(screen.getByText("switch"));
    expect(screen.getByText("ಹವಾಮಾನ")).toBeInTheDocument();
    expect(localStorage.getItem("krishimitra_ui_language")).toBe("kn");
    expect(document.documentElement.lang).toBe("kn");
  });

  it("starts in the remembered language", () => {
    localStorage.setItem("krishimitra_ui_language", "ta");
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("lang")).toHaveTextContent("ta");
    expect(screen.getByText("வானிலை")).toBeInTheDocument();
  });
});

describe("first-time guide", () => {
  beforeEach(() => localStorage.setItem("krishimitra_ui_language", "te"));

  it("walks through the steps in the chosen language", async () => {
    let closed = false;
    render(
      <I18nProvider>
        <UserGuide open onClose={() => (closed = true)} />
      </I18nProvider>,
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("KrishiMitra కు స్వాగతం");
    expect(screen.getByText("{n} లో {i} వ దశ".replace("{n}", "6").replace("{i}", "1"))).toBeInTheDocument();
    await userEvent.click(screen.getByText("తర్వాత"));
    expect(screen.getByRole("dialog")).toHaveTextContent("1. మాట్లాడి అడగండి");
    for (let i = 0; i < 4; i++) await userEvent.click(screen.getByText("తర్వాత"));
    await act(async () => userEvent.click(screen.getByText("వాడటం ప్రారంభించండి")));
    expect(closed).toBe(true);
  });

  it("has a shorter admin version", () => {
    render(
      <I18nProvider>
        <UserGuide open isAdmin onClose={() => {}} />
      </I18nProvider>,
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("అడ్మిన్ అవలోకనం");
  });

  it("plays the demo video from the guide and goes back", async () => {
    const { container } = render(
      <I18nProvider>
        <UserGuide open onClose={() => {}} />
      </I18nProvider>,
    );
    await userEvent.click(screen.getByText("డెమో వీడియో చూడండి (3 నిమి.)"));
    const video = container.querySelector("video");
    expect(video).toHaveAttribute("src", "/demo/krishimitra_demo_te.mp4");
    expect(screen.getByRole("dialog")).toHaveTextContent("KrishiMitra ఎలా వాడాలి – డెమో వీడియో");
    await userEvent.click(screen.getByText("గైడ్‌కు తిరిగి వెళ్ళండి"));
    expect(container.querySelector("video")).toBeNull();
    expect(screen.getByRole("dialog")).toHaveTextContent("KrishiMitra కు స్వాగతం");
  });

  it("picks the demo video in the app language, English otherwise", () => {
    expect(demoVideoFor("hi").src).toBe("/demo/krishimitra_demo_hi.mp4");
    expect(demoVideoFor("ur").poster).toBe("/demo/krishimitra_demo_ur.jpg");
    expect(demoVideoFor("xx").src).toBe("/demo/krishimitra_demo_en.mp4");
  });
});
