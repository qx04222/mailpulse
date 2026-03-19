import { createAdminClient } from "@/lib/supabase";

export async function GET() {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("digest_runs")
    .select("*, companies(id, name)")
    .order("started_at", { ascending: false });

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const reports = data.map((r: Record<string, unknown>) => ({
    ...r,
    company: r.companies,
  }));

  return Response.json(reports);
}
