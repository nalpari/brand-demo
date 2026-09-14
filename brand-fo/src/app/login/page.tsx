"use client";

import { useActionState } from "react";
import { login } from "@/app/actions";

export default function LoginPage() {
  const [error, action, pending] = useActionState(login, undefined);

  return (
    <main className="flex flex-1 items-center justify-center">
      <form action={action} className="flex w-72 flex-col gap-3">
        <h1 className="text-xl font-semibold">로그인</h1>
        <label className="flex flex-col gap-1 text-sm">
          아이디
          <input
            name="username"
            autoComplete="username"
            required
            className="rounded border px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          비밀번호
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="rounded border px-3 py-2"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button
          disabled={pending}
          className="rounded bg-foreground px-3 py-2 text-background disabled:opacity-50"
        >
          로그인
        </button>
      </form>
    </main>
  );
}
