"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { API_URL, TOKEN_COOKIE } from "@/lib/session";

export async function login(
  _prev: string | undefined,
  formData: FormData,
): Promise<string | undefined> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: formData.get("username"),
      password: formData.get("password"),
    }),
  });
  // 400(빈 값)과 401(틀린 계정·비번)을 같은 문구로 — 어느 필드인지 드러내지 않는다
  if (res.status === 400 || res.status === 401) {
    return "아이디 또는 비밀번호가 올바르지 않습니다.";
  }
  if (!res.ok) throw new Error(`POST /api/auth/login failed: ${res.status}`);

  const { token, expiresAt } = await res.json();
  (await cookies()).set(TOKEN_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires: new Date(expiresAt),
  });
  redirect("/");
}

export async function logout() {
  (await cookies()).delete(TOKEN_COOKIE);
  redirect("/login");
}
