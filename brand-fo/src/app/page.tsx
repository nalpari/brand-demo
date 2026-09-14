import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { logout } from "@/app/actions";
import { SessionExpired } from "@/app/session-expired";
import { API_URL, TOKEN_COOKIE } from "@/lib/session";

export default async function Home() {
  const token = (await cookies()).get(TOKEN_COOKIE)?.value;
  if (!token) redirect("/login");

  const res = await fetch(`${API_URL}/api/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  // 만료·비번 변경·삭제로 무효가 된 토큰
  if (res.status === 401) return <SessionExpired />;
  if (!res.ok) throw new Error(`GET /api/users/me failed: ${res.status}`);

  const me: { username: string } = await res.json();

  return (
    <main className="flex flex-1 items-center justify-center">
      <form action={logout} className="flex flex-col items-center gap-3">
        <p>
          <strong>{me.username}</strong> 로 로그인됨
        </p>
        <button className="rounded border px-3 py-2">로그아웃</button>
      </form>
    </main>
  );
}
