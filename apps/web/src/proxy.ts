import { NextRequest, NextResponse } from "next/server";
export function proxy(request: NextRequest) { if (request.nextUrl.pathname === "/admin" && !request.cookies.has("little_orbit_admin")) return NextResponse.redirect(new URL("/admin/login", request.url)); return NextResponse.next(); }
export const config = { matcher: ["/admin"] };
