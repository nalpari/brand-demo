import { NextResponse, type NextRequest } from "next/server";
import { TOKEN_COOKIE } from "@/lib/session";

// 쿠키 유무만 보는 낙관적 체크. 토큰이 실제로 유효한지는 `/` 페이지의 /api/users/me 호출이 판정한다.
export function proxy(request: NextRequest) {
  const hasToken = request.cookies.has(TOKEN_COOKIE);
  const isLogin = request.nextUrl.pathname === "/login";

  if (!hasToken && !isLogin) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (hasToken && isLogin) {
    return NextResponse.redirect(new URL("/", request.url));
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
