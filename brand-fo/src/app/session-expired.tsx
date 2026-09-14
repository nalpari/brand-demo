"use client";

import { startTransition, useEffect, useRef } from "react";
import { logout } from "@/app/actions";

// Server Component 렌더 중에는 쿠키를 지울 수 없어서, 마운트되자마자 logout 서버 액션을 부른다.
// JS가 없으면 버튼으로 같은 액션을 제출한다.
export function SessionExpired() {
  // StrictMode가 effect를 두 번 돌리면 두 번째 호출이 /login 으로 이동한 뒤 나가서 깨진다
  const called = useRef(false);
  useEffect(() => {
    if (called.current) return;
    called.current = true;
    startTransition(logout);
  }, []);

  return (
    <main className="flex flex-1 items-center justify-center">
      <form action={logout} className="flex flex-col items-center gap-3">
        <p>세션이 만료되었습니다.</p>
        <button className="rounded border px-3 py-2">다시 로그인</button>
      </form>
    </main>
  );
}
