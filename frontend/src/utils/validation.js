// Client-side checks mirror the backend rules so users see errors before submitting.
// The backend validates again; these are for convenience, not security.

export function normalisePhone(value) {
  let digits = (value || "").replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  return digits;
}

export function validatePhone(value) {
  return /^[6-9]\d{9}$/.test(normalisePhone(value)) ? null : "Enter a valid 10-digit mobile number";
}

export function validatePassword(value) {
  if (!value || value.length < 8) return "At least 8 characters";
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) return "Use at least one letter and one number";
  return null;
}

export function validateEmail(value) {
  if (!value) return null; // optional
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? null : "Enter a valid email";
}

export function validateRegistration(form) {
  const errors = {};
  if (!form.full_name || form.full_name.trim().length < 2) errors.full_name = "Enter your name";
  const phone = validatePhone(form.phone);
  if (phone) errors.phone = phone;
  const email = validateEmail(form.email);
  if (email) errors.email = email;
  const pw = validatePassword(form.password);
  if (pw) errors.password = pw;
  if (form.password !== form.confirm) errors.confirm = "Passwords do not match";
  return errors;
}
