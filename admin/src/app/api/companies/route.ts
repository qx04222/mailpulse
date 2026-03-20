import { createAdminClient } from "@/lib/supabase";

export async function GET() {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("companies")
    .select("*, company_members(person_id, people(id, name, email, role))")
    .order("name");

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const companies = data.map((c: Record<string, unknown>) => ({
    ...c,
    members: (c.company_members as Record<string, unknown>[])?.map(
      (cm: Record<string, unknown>) => cm.people
    ) ?? [],
  }));

  return Response.json(companies);
}

export async function POST(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const { name, gmail_label, telegram_group_id, lark_group_id, is_active } = body;

  const { data, error } = await supabase
    .from("companies")
    .insert({ name, gmail_label, telegram_group_id, lark_group_id, is_active: is_active ?? true })
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data, { status: 201 });
}

export async function PUT(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const { id, name, gmail_label, telegram_group_id, lark_group_id, is_active } = body;

  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("companies")
    .update({ name, gmail_label, telegram_group_id, lark_group_id, is_active })
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

  await supabase.from("company_members").delete().eq("company_id", id);
  const { error } = await supabase.from("companies").delete().eq("id", id);

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json({ success: true });
}
