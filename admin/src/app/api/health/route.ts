import { createAdminClient } from "@/lib/supabase";

export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || "(not set)";
  const hasServiceKey = !!process.env.SUPABASE_SERVICE_KEY;

  let dbTest = "not tested";
  try {
    const supabase = createAdminClient();
    const { data, error } = await supabase.from("companies").select("name").limit(3);
    if (error) {
      dbTest = `error: ${error.message}`;
    } else {
      dbTest = `ok: ${(data || []).map((c: { name: string }) => c.name).join(", ")}`;
    }
  } catch (e) {
    dbTest = `exception: ${e}`;
  }

  return Response.json({
    supabase_url: url,
    has_service_key: hasServiceKey,
    service_key_prefix: process.env.SUPABASE_SERVICE_KEY?.slice(0, 20) || "(empty)",
    db_test: dbTest,
  });
}
