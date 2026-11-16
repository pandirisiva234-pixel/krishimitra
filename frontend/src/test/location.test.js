import { afterEach, describe, expect, it, vi } from "vitest";
import { getCurrentLocation } from "../utils/location";

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("getCurrentLocation", () => {
  it("returns the device position and remembers it", async () => {
    const getCurrentPosition = vi.fn((ok) => ok({ coords: { latitude: 12.971599, longitude: 77.594566 } }));
    vi.stubGlobal("navigator", { geolocation: { getCurrentPosition } });
    expect(await getCurrentLocation()).toEqual({ lat: 12.9716, lon: 77.5946 });
    await getCurrentLocation(); // second call uses the remembered position
    expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    await getCurrentLocation({ fresh: true }); // "Use my current location" asks again
    expect(getCurrentPosition).toHaveBeenCalledTimes(2);
  });

  it("gives null when permission is refused", async () => {
    vi.stubGlobal("navigator", { geolocation: { getCurrentPosition: (ok, fail) => fail({ code: 1 }) } });
    expect(await getCurrentLocation()).toBeNull();
  });
});
