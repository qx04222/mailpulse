import { createAdminClient } from "@/lib/supabase";
import { type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const supabase = createAdminClient();
  const searchParams = request.nextUrl.searchParams;
  const companyId = searchParams.get("company_id");
  const eventType = searchParams.get("event_type");
  const severity = searchParams.get("severity");
  const isRead = searchParams.get("is_read");

  let query = supabase
    .from("events")
    .select("*, companies(id, name), clients(id, name, email), people(id, name)")
    .order("created_at", { ascending: false })
    .limit(100);

  if (companyId) {
    query = query.eq("company_id", companyId);
  }
  if (eventType) {
    query = query.eq("event_type", eventType);
  }
  if (severity) {
    query = query.eq("severity", severity);
  }
  if (isRead === "false") {
    query = query.eq("is_read", false);
  }

  const { data, error } = await query;

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const events = (data ?? []).map((e: Record<string, unknown>) => ({
    ...e,
    company: e.companies,
    client: e.clients,
    person: e.people,
  }));

  return Response.json(events);
}

export async function PUT(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const { id, is_read, is_resolved } = body;

  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  const updates: Record<string, unknown> = {};
  if (is_read !== undefined) updates.is_read = is_read;
  if (is_resolved !== undefined) updates.is_resolved = is_resolved;

  const { data, error } = await supabase
    .from("events")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data);
}
