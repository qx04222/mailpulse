import { cookies } from "next/headers";

export async function POST(request: Request) {
  const body = await request.json();
  const { password } = body;

  if (!password) {
    return Response.json({ error: "Password is required" }, { status: 400 });
  }

  if (password !== process.env.ADMIN_PASSWORD) {
    return Response.json({ error: "Invalid password" }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set("admin_session", "authenticated", {
    httpOnly: true,
    path: "/",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7, // 7 days
  });

  return Response.json({ success: true });
}
