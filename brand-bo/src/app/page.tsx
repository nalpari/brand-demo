import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, fetchMe } from "@/lib/auth";
import { logout } from "./actions";

export default async function Home() {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const me = token ? await fetchMe(token) : null;
  // Rendering cannot delete the cookie, so a Route Handler clears it on the way to /login.
  if (me?.role !== "ADMIN") redirect("/session/clear");

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4">
      <p>
        <strong>{me.username}</strong> (관리자) 로 로그인됨
      </p>
      <form action={logout}>
        <button className="rounded border px-3 py-2">로그아웃</button>
      </form>
    </main>
  );
}
