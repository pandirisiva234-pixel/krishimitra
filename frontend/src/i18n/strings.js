import bn from "./locales/bn.js";
import en from "./locales/en.js";
import gu from "./locales/gu.js";
import hi from "./locales/hi.js";
import kn from "./locales/kn.js";
import ml from "./locales/ml.js";
import mr from "./locales/mr.js";
import ta from "./locales/ta.js";
import te from "./locales/te.js";
import ur from "./locales/ur.js";

export const STRINGS = { en, te, hi, kn, ta, ml, mr, bn, gu, ur };

// Fixed English messages produced outside React (form checks, microphone errors) -> interface keys
export const MESSAGE_KEYS = {
  "Enter your name": "valid.name",
  "Enter a valid 10-digit mobile number": "valid.phone",
  "At least 8 characters": "valid.pwLength",
  "Use at least one letter and one number": "valid.pwMix",
  "Enter a valid email": "valid.email",
  "Passwords do not match": "valid.noMatch",
  "This browser cannot record audio. Use Chrome, Edge or Firefox, or type your question.": "mic.noSupport",
  "Microphone permission was denied. Allow it in the browser address bar and try again.": "mic.denied",
  "Could not start the microphone. Check that one is connected.": "mic.failed",
};
