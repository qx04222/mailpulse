import { createAdminClient } from "@/lib/supabase";

export async function GET() {
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("sla_configs")
    .select("*, companies(id, name)")
    .order("created_at", { ascending: false });

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const configs = (data ?? []).map((c: Record<string, unknown>) => ({
    ...c,
    company: c.companies,
  }));

  return Response.json(configs);
}

export async function POST(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const {
    company_id,
    first_response_hours,
    followup_response_hours,
    escalate_after_hours,
    escalate_to,
  } = body;

  if (!company_id) {
    return Response.json({ error: "company_id is required" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("sla_configs")
    .insert({
      company_id,
      first_response_hours: first_response_hours ?? 4,
      followup_response_hours: followup_response_hours ?? 24,
      escalate_after_hours: escalate_after_hours ?? 48,
      escalate_to: escalate_to ?? null,
    })
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data);
}

export async function PUT(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const { id, ...updates } = body;

  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("sla_configs")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data);
}
