import { createAdminClient } from "@/lib/supabase";

export async function GET() {
  const supabase = createAdminClient();

  const [companies, people, threads, actionItems, digestRuns] =
    await Promise.all([
      supabase.from("companies").select("id", { count: "exact", head: true }),
      supabase.from("people").select("id", { count: "exact", head: true }),
      supabase.from("threads").select("id", { count: "exact", head: true }),
      supabase.from("action_items").select("id", { count: "exact", head: true }),
      supabase
        .from("digest_runs")
        .select("*, companies(name)")
        .order("started_at", { ascending: false })
        .limit(10),
    ]);

  return Response.json({
    totalCompanies: companies.count ?? 0,
    totalPeople: people.count ?? 0,
    totalEmails: threads.count ?? 0,
    totalActionItems: actionItems.count ?? 0,
    recentRuns: (digestRuns.data ?? []).map((r: Record<string, unknown>) => ({
      ...r,
      company: r.companies,
    })),
  });
}
