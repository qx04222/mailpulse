import { createAdminClient } from "@/lib/supabase";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: companyId } = await params;
  const supabase = createAdminClient();
  const body = await request.json();
  const { action, person_id } = body;

  if (!person_id) {
    return Response.json({ error: "person_id is required" }, { status: 400 });
  }

  if (action === "add") {
    const { error } = await supabase
      .from("company_members")
      .insert({ company_id: companyId, person_id });

    if (error) {
      return Response.json({ error: error.message }, { status: 500 });
    }
    return Response.json({ success: true }, { status: 201 });
  }

  if (action === "remove") {
    const { error } = await supabase
      .from("company_members")
      .delete()
      .eq("company_id", companyId)
      .eq("person_id", person_id);

    if (error) {
      return Response.json({ error: error.message }, { status: 500 });
    }
    return Response.json({ success: true });
  }

  return Response.json({ error: "Invalid action. Use 'add' or 'remove'" }, { status: 400 });
}
