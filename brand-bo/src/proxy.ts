import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth";

// Optimistic only: whether the cookie holds a valid ADMIN token is decided by /api/users/me.
export function proxy(request: NextRequest) {
  const hasToken = request.cookies.has(SESSION_COOKIE);
  const onLogin = request.nextUrl.pathname === "/login";

  if (!hasToken && !onLogin) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (hasToken && onLogin) {
    return NextResponse.redirect(new URL("/", request.url));
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
