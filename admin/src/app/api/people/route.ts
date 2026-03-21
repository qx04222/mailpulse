import { createAdminClient } from "@/lib/supabase";

export async function GET() {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("people")
    .select("*, company_members(company_id, companies(id, name))")
    .order("name");

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const people = data.map((p: Record<string, unknown>) => ({
    ...p,
    companies: (p.company_members as Record<string, unknown>[])?.map(
      (cm: Record<string, unknown>) => cm.companies
    ) ?? [],
  }));

  return Response.json(people);
}
