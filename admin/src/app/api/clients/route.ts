import { createAdminClient } from "@/lib/supabase";
import { type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const supabase = createAdminClient();
  const searchParams = request.nextUrl.searchParams;
  const companyId = searchParams.get("company_id");

  // Build base query
  let query = supabase
    .from("clients")
    .select("*")
    .order("last_activity_at", { ascending: false });

  if (companyId) {
    const { data: threads } = await supabase
      .from("threads")
      .select("client_id")
      .eq("company_id", companyId);

    const clientIds = [
      ...new Set(
        (threads ?? [])
          .map((t: Record<string, unknown>) => t.client_id)
          .filter(Boolean)
      ),
    ];
    if (clientIds.length === 0) return Response.json([]);
    query = query.in("id", clientIds as string[]);
  }

  const { data: clients, error } = await query;
  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  // Fetch all client-company associations via threads
  const clientIds = (clients ?? []).map(
    (c: Record<string, unknown>) => c.id as string
  );
  if (clientIds.length === 0) return Response.json([]);

  const { data: threads } = await supabase
    .from("threads")
    .select("client_id, company_id, companies(id, name)")
    .in("client_id", clientIds);

  // Build client → companies map (deduplicated)
  const clientCompanyMap = new Map<
    string,
    { id: string; name: string }[]
  >();
  for (const t of threads ?? []) {
    const rec = t as Record<string, unknown>;
    const clientId = rec.client_id as string;
    const company = rec.companies as { id: string; name: string } | null;
    if (!clientId || !company) continue;

    if (!clientCompanyMap.has(clientId)) {
      clientCompanyMap.set(clientId, []);
    }
    const list = clientCompanyMap.get(clientId)!;
    if (!list.some((c) => c.id === company.id)) {
      list.push(company);
    }
  }

  // Merge companies into client objects
  const enriched = (clients ?? []).map((c: Record<string, unknown>) => ({
    ...c,
    companies: clientCompanyMap.get(c.id as string) ?? [],
  }));

  return Response.json(enriched);
}
