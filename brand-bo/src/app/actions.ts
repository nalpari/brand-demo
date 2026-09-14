"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { API_URL, SESSION_COOKIE, fetchMe } from "@/lib/auth";

export async function login(_prev: string, formData: FormData): Promise<string> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: formData.get("username"),
      password: formData.get("password"),
    }),
  });
  // Neither message says which field was wrong.
  if (res.status === 400) return "아이디와 비밀번호를 입력하세요.";
  if (res.status === 401) return "아이디 또는 비밀번호가 올바르지 않습니다.";
  if (!res.ok) throw new Error(`POST /api/auth/login failed: ${res.status}`);

  const { token, expiresAt } = await res.json();
  // role is not a token claim, only /me knows it. A non-admin token is dropped, never stored.
  if ((await fetchMe(token))?.role !== "ADMIN") return "관리자 권한이 없습니다.";

  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires: new Date(expiresAt),
  });
  redirect("/");
}

export async function logout() {
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/login");
}
