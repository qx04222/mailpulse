import { createAdminClient } from "@/lib/supabase";
import { type NextRequest } from "next/server";

export async function GET() {
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("email_templates")
    .select("*, companies(id, name)")
    .order("created_at", { ascending: false });

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const templates = (data ?? []).map((t: Record<string, unknown>) => ({
    ...t,
    company: t.companies,
  }));

  return Response.json(templates);
}

export async function POST(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const { name, subject, body: templateBody, category, company_id, variables } = body;

  if (!name || !subject) {
    return Response.json({ error: "name and subject are required" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("email_templates")
    .insert({
      name,
      subject,
      body: templateBody ?? "",
      category: category ?? "other",
      company_id: company_id || null,
      variables: variables ?? [],
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
    .from("email_templates")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data);
}

export async function DELETE(request: NextRequest) {
  const supabase = createAdminClient();
  const id = request.nextUrl.searchParams.get("id");

  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  const { error } = await supabase.from("email_templates").delete().eq("id", id);

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json({ success: true });
}
