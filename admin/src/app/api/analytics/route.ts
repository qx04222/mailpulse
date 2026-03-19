import { createAdminClient } from "@/lib/supabase";
import { type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const supabase = createAdminClient();
  const type = request.nextUrl.searchParams.get("type") ?? "volume";

  try {
    switch (type) {
      case "volume": {
        const { data: companies } = await supabase
          .from("companies")
          .select("id, name");
        const { data: runs } = await supabase
          .from("digest_runs")
          .select("company_id, total_emails, started_at")
          .order("started_at", { ascending: false })
          .limit(200);

        // Group by week and company
        const weekMap: Record<string, Record<string, number>> = {};
        for (const run of runs ?? []) {
          const r = run as Record<string, unknown>;
          const date = new Date(r.started_at as string);
          const weekStart = new Date(date);
          weekStart.setDate(date.getDate() - date.getDay());
          const weekKey = weekStart.toISOString().slice(0, 10);
          if (!weekMap[weekKey]) weekMap[weekKey] = {};
          const companyName =
            (companies ?? []).find(
              (c: Record<string, unknown>) => c.id === r.company_id
            )?.name ?? "Unknown";
          weekMap[weekKey][companyName as string] =
            (weekMap[weekKey][companyName as string] ?? 0) +
            (r.total_emails as number);
        }

        const volumeData = Object.entries(weekMap)
          .sort(([a], [b]) => a.localeCompare(b))
          .slice(-4)
          .map(([week, companyData]) => ({ week, ...companyData }));

        return Response.json({
          data: volumeData,
          companies: (companies ?? []).map(
            (c: Record<string, unknown>) => c.name
          ),
        });
      }

      case "response_time": {
        // Return sample structure - real implementation would compute from emails table
        const { data: runs } = await supabase
          .from("digest_runs")
          .select("started_at, total_emails")
          .order("started_at", { ascending: false })
          .limit(28);

        const weeks: Record<string, { total: number; count: number }> = {};
        for (const run of runs ?? []) {
          const r = run as Record<string, unknown>;
          const date = new Date(r.started_at as string);
          const weekStart = new Date(date);
          weekStart.setDate(date.getDate() - date.getDay());
          const weekKey = weekStart.toISOString().slice(0, 10);
          if (!weeks[weekKey]) weeks[weekKey] = { total: 0, count: 0 };
          weeks[weekKey].total += Math.random() * 24; // placeholder
          weeks[weekKey].count += 1;
        }

        const responseData = Object.entries(weeks)
          .sort(([a], [b]) => a.localeCompare(b))
          .slice(-4)
          .map(([week, { total, count }]) => ({
            week,
            avgHours: count > 0 ? Math.round((total / count) * 10) / 10 : 0,
          }));

        return Response.json({ data: responseData });
      }

      case "workload": {
        const { data: people } = await supabase
          .from("people")
          .select("id, name");
        const { data: items } = await supabase
          .from("action_items")
          .select("assigned_to_id")
          .in("status", ["pending", "in_progress"]);

        const counts: Record<string, number> = {};
        for (const item of items ?? []) {
          const i = item as Record<string, unknown>;
          const personName =
            (people ?? []).find(
              (p: Record<string, unknown>) => p.id === i.assigned_to_id
            )?.name ?? "Unassigned";
          counts[personName as string] =
            (counts[personName as string] ?? 0) + 1;
        }

        const workloadData = Object.entries(counts).map(([name, value]) => ({
          name,
          value,
        }));

        return Response.json({ data: workloadData });
      }

      case "funnel": {
        const statuses = [
          "lead",
          "active",
          "quoted",
          "negotiating",
          "closed",
        ];
        const funnelData: { status: string; count: number }[] = [];

        for (const status of statuses) {
          const { count } = await supabase
            .from("clients")
            .select("id", { count: "exact", head: true })
            .eq("status", status);
          funnelData.push({ status, count: count ?? 0 });
        }

        return Response.json({ data: funnelData });
      }

      case "comparison": {
        const { data: companies } = await supabase
          .from("companies")
          .select("id, name");

        const comparisonData: Record<string, unknown>[] = [];
        for (const company of companies ?? []) {
          const c = company as Record<string, unknown>;
          const { count: threads } = await supabase
            .from("threads")
            .select("id", { count: "exact", head: true })
            .eq("company_id", c.id as string);
          const { count: actions } = await supabase
            .from("action_items")
            .select("id", { count: "exact", head: true })
            .eq("company_id", c.id as string);
          const { count: runs } = await supabase
            .from("digest_runs")
            .select("id", { count: "exact", head: true })
            .eq("company_id", c.id as string);

          comparisonData.push({
            name: c.name,
            threads: threads ?? 0,
            actionItems: actions ?? 0,
            digestRuns: runs ?? 0,
          });
        }

        return Response.json({ data: comparisonData });
      }

      default:
        return Response.json({ error: "Invalid type" }, { status: 400 });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return Response.json({ error: message }, { status: 500 });
  }
}
