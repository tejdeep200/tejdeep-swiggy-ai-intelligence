// Docker's internal request URL can use 0.0.0.0 while the browser uses
// localhost. Compare with the actual HTTP Host header, not the bind address.
export function isSameOrigin(origin: string, host: string | null, requestUrl: string): boolean {
  if (!host) return false;
  try {
    const expected = new URL(requestUrl);
    expected.host = host;
    return new URL(origin).origin === expected.origin;
  } catch {
    return false;
  }
}
