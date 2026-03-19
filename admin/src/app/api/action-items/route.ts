import { createAdminClient } from "@/lib/supabase";
import { type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const supabase = createAdminClient();
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get("status");
  const companyId = searchParams.get("company_id");
  const assignedTo = searchParams.get("assigned_to");

  let query = supabase
    .from("action_items")
    .select("*, companies(id, name), people(id, name)")
    .order("created_at", { ascending: false });

  if (status) {
    query = query.eq("status", status);
  }
  if (companyId) {
    query = query.eq("company_id", companyId);
  }
  if (assignedTo) {
    query = query.eq("assigned_to_id", assignedTo);
  }

  const { data, error } = await query;

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const items = data.map((item: Record<string, unknown>) => ({
    ...item,
    company: item.companies,
    assigned_to: item.people,
  }));

  return Response.json(items);
}

export async function PUT(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const { id, status, assigned_to_id, priority, due_date } = body;

  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  const updates: Record<string, unknown> = {};
  if (status !== undefined) updates.status = status;
  if (assigned_to_id !== undefined) updates.assigned_to_id = assigned_to_id;
  if (priority !== undefined) updates.priority = priority;
  if (due_date !== undefined) updates.due_date = due_date;

  const { data, error } = await supabase
    .from("action_items")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data);
}
