import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RelatedVideos, { formatDuration } from "../components/RelatedVideos";

// videos() is a plain function that calls the spy, except in the failure test, where a plain function
// returns the rejected promise (a rejecting spy is reported by the test runner as an error)
const api = vi.hoisted(() => ({ fail: false }));
vi.mock("../api/endpoints", () => {
  const spy = vi.fn();
  return {
    assistant: {
      spy,
      videos: (...args) => (api.fail ? Promise.reject(new Error("quota")) : spy(...args)),
    },
  };
});
import { assistant as realAssistant } from "../api/endpoints";
const assistant = { videos: realAssistant.spy };

const VIDEOS = {
  enabled: true,
  videos: [
    { video_id: "ccc", title: "Fall armyworm control", channel: "DD Kisan", url: "https://www.youtube.com/watch?v=ccc",
      thumbnail_url: "https://i.ytimg.com/vi/ccc/mqdefault.jpg", duration_seconds: 725, trusted: true },
    { video_id: "aaa", title: "Maize pest tips", channel: "Farm Vlogs", url: "https://www.youtube.com/watch?v=aaa",
      thumbnail_url: null, duration_seconds: 300, trusted: false },
  ],
};

describe("RelatedVideos", () => {
  beforeEach(() => {
    assistant.videos.mockClear();
    api.fail = false;
  });

  it("formats durations", () => {
    expect(formatDuration(725)).toBe("12:05");
    expect(formatDuration(59)).toBe("0:59");
  });

  it("loads videos for a new answer and marks trusted channels", async () => {
    assistant.videos.mockResolvedValue(VIDEOS);
    render(<RelatedVideos question="fall armyworm in maize" original="మొక్కజొన్నలో కత్తెర పురుగు" languageCode="te" intent="pest" autoLoad />);
    expect(await screen.findByText("Fall armyworm control")).toBeInTheDocument();
    expect(assistant.videos).toHaveBeenCalledWith("fall armyworm in maize", "te", "మొక్కజొన్నలో కత్తెర పురుగు");
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("href", "https://www.youtube.com/watch?v=ccc");
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("target", "_blank");
    expect(screen.getByText("Trusted")).toBeInTheDocument();
    expect(screen.getByText("12:05")).toBeInTheDocument();
  });

  it("waits for a click on older answers", async () => {
    assistant.videos.mockResolvedValue(VIDEOS);
    render(<RelatedVideos question="rice blast" languageCode="kn" intent="disease" />);
    expect(assistant.videos).not.toHaveBeenCalled();
    await userEvent.click(screen.getByText("Show related videos"));
    expect(await screen.findByText("Maize pest tips")).toBeInTheDocument();
  });

  it("is hidden for price answers", () => {
    const { container } = render(<RelatedVideos question="tomato price" intent="market_price" autoLoad />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is hidden for greetings and weather", () => {
    const { container } = render(<RelatedVideos question="hello" intent="greeting" autoLoad />);
    expect(container).toBeEmptyDOMElement();
    expect(assistant.videos).not.toHaveBeenCalled();
  });

  it("is hidden when the server has no YouTube key", async () => {
    assistant.videos.mockResolvedValue({ enabled: false, videos: [] });
    const { container } = render(<RelatedVideos question="tomato blight" languageCode="hi" intent="disease" autoLoad />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("is hidden when YouTube fails", async () => {
    api.fail = true;
    const { container } = render(<RelatedVideos question="tomato blight" languageCode="hi" intent="disease" autoLoad />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
