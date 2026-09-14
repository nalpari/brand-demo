export const SESSION_COOKIE = "bo_token";

export const API_URL = process.env.BRAND_API_URL ?? "http://localhost:8080";

// null when the backend no longer accepts the token (expired, password changed, account deleted).
export async function fetchMe(
  token: string,
): Promise<{ username: string; role: string } | null> {
  const res = await fetch(`${API_URL}/api/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`GET /api/users/me failed: ${res.status}`);
  return res.json();
}
