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

export async function POST(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const { name, email, role, telegram_user_id, lark_user_id, is_active, company_ids } = body;

  const { data, error } = await supabase
    .from("people")
    .insert({ name, email, role, telegram_user_id, lark_user_id, is_active: is_active ?? true })
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  if (company_ids && company_ids.length > 0) {
    const memberships = company_ids.map((companyId: string) => ({
      person_id: data.id,
      company_id: companyId,
    }));
    await supabase.from("company_members").insert(memberships);
  }

  return Response.json(data, { status: 201 });
}

export async function PUT(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const { id, name, email, role, telegram_user_id, lark_user_id, is_active, company_ids } = body;

  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("people")
    .update({ name, email, role, telegram_user_id, lark_user_id, is_active })
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  if (company_ids !== undefined) {
    await supabase.from("company_members").delete().eq("person_id", id);
    if (company_ids.length > 0) {
      const memberships = company_ids.map((companyId: string) => ({
        person_id: id,
        company_id: companyId,
      }));
      await supabase.from("company_members").insert(memberships);
    }
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

  await supabase.from("company_members").delete().eq("person_id", id);
  const { error } = await supabase.from("people").delete().eq("id", id);

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json({ success: true });
}
