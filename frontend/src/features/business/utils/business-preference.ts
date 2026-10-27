const KEY = "taxpilot.business.active.v1";
export function readBusinessPreference() { if (typeof window === "undefined") return null; const value = window.localStorage.getItem(KEY); return value?.trim() || null; }
export function writeBusinessPreference(id: string) { if (typeof window !== "undefined") window.localStorage.setItem(KEY, id); }
export function clearBusinessPreference() { if (typeof window !== "undefined") window.localStorage.removeItem(KEY); }
