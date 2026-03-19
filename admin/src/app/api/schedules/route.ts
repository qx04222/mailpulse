import { createAdminClient } from "@/lib/supabase";

export async function GET() {
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("digest_schedules")
    .select("*, companies(id, name), people!digest_schedules_target_person_id_fkey(id, name, email)")
    .order("created_at", { ascending: false });

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const schedules = (data ?? []).map((s: Record<string, unknown>) => ({
    ...s,
    company: s.companies,
    target_person: s.people,
  }));

  return Response.json(schedules);
}

export async function POST(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const {
    name,
    cron_expression,
    timezone,
    company_id,
    target_type,
    target_group_id,
    target_person_id,
    report_type,
    include_sections,
    lookback_days,
    is_active,
  } = body;

  if (!name || !cron_expression) {
    return Response.json(
      { error: "name and cron_expression are required" },
      { status: 400 }
    );
  }

  const { data, error } = await supabase
    .from("digest_schedules")
    .insert({
      name,
      cron_expression,
      timezone: timezone ?? "America/Toronto",
      company_id: company_id || null,
      target_type: target_type ?? "group",
      target_group_id: target_group_id || null,
      target_person_id: target_person_id || null,
      report_type: report_type ?? "brief",
      include_sections: include_sections ?? [],
      lookback_days: lookback_days ?? 3,
      is_active: is_active ?? true,
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

  // Remove joined fields before updating
  delete updates.company;
  delete updates.target_person;
  delete updates.companies;
  delete updates.people;

  const { data, error } = await supabase
    .from("digest_schedules")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data);
}

export async function DELETE(request: Request) {
  const supabase = createAdminClient();
  const { searchParams } = new URL(request.url);
  const id = searchParams.get("id");

  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  const { error } = await supabase
    .from("digest_schedules")
    .delete()
    .eq("id", id);

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json({ success: true });
}
