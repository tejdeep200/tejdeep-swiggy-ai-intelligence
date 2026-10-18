// Docker's internal request URL can use 0.0.0.0 while the browser uses
// localhost. Compare with the actual HTTP Host header, not the bind address.
export function isSameOrigin(origin: string, host: string | null, requestUrl: string, protocol?: 'http:' | 'https:'): boolean {
  if (!host) return false;
  try {
    const expected = new URL(requestUrl);
    expected.host = host;
    if (protocol) expected.protocol = protocol;
    return new URL(origin).origin === expected.origin;
  } catch {
    return false;
  }
}
