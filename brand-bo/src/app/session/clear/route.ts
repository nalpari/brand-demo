import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, fetchMe } from "@/lib/auth";

// "/" sends a dead or demoted session here, because a Server Component cannot write cookies.
// Any cross-site link can trigger a GET, so a session that still passes /me is kept.
export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  if (token && (await fetchMe(token))?.role === "ADMIN") redirect("/");

  cookieStore.delete(SESSION_COOKIE);
  redirect("/login");
}
