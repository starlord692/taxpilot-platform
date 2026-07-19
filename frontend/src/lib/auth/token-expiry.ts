export const TOKEN_EXPIRY_SKEW_MS = 5_000;
export function getExpiresAt(expiresInSeconds: number, now = Date.now()) { return now + expiresInSeconds * 1_000; }
export function isSessionExpired(expiresAt: number, now = Date.now()) { return !Number.isFinite(expiresAt) || expiresAt <= now + TOKEN_EXPIRY_SKEW_MS; }
