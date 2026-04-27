// User-supplied HuggingFace write token. Only needed when submitting a
// prediction PR — public dataset reads work anonymously. Stored in
// localStorage under a single key; never sent anywhere except huggingface.co
// via @huggingface/hub.

const KEY = "hf-write-token";

export function getStoredHfToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  const v = localStorage.getItem(KEY);
  return v && v.trim() ? v.trim() : null;
}

export function setStoredHfToken(token: string): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(KEY, token.trim());
}

export function clearStoredHfToken(): void {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(KEY);
}

export const HF_TOKEN_URL = "https://huggingface.co/settings/tokens";
export const HF_SIGNUP_URL = "https://huggingface.co/join";
