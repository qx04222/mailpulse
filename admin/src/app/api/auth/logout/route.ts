import { cookies } from "next/headers";

export async function POST() {
  const cookieStore = await cookies();
  cookieStore.set("admin_session", "", {
    httpOnly: true,
    path: "/",
    maxAge: 0,
  });

  return Response.json({ success: true });
}
