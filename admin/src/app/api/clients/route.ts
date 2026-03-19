import { createAdminClient } from "@/lib/supabase";
import { type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const supabase = createAdminClient();
  const searchParams = request.nextUrl.searchParams;
  const companyId = searchParams.get("company_id");

  let query = supabase.from("clients").select("*").order("last_activity_at", { ascending: false });

  if (companyId) {
    // Filter clients by company through threads
    const { data: threads } = await supabase
      .from("threads")
      .select("client_id")
      .eq("company_id", companyId);

    const clientIds = [...new Set((threads ?? []).map((t: Record<string, unknown>) => t.client_id).filter(Boolean))];
    if (clientIds.length > 0) {
      query = query.in("id", clientIds);
    } else {
      return Response.json([]);
    }
  }

  const { data, error } = await query;

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data);
}
