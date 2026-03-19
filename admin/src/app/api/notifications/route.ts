import { createAdminClient } from "@/lib/supabase";
import { type NextRequest } from "next/server";

export async function GET() {
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("notification_rules")
    .select("*")
    .order("created_at", { ascending: false });

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data ?? []);
}

export async function POST(request: Request) {
  const supabase = createAdminClient();
  const body = await request.json();
  const {
    channel,
    event_types,
    min_severity,
    only_assigned,
    quiet_hours_start,
    quiet_hours_end,
    is_active,
  } = body;

  const { data, error } = await supabase
    .from("notification_rules")
    .insert({
      channel: channel ?? "email",
      event_types: event_types ?? [],
      min_severity: min_severity ?? "info",
      only_assigned: only_assigned ?? false,
      quiet_hours_start: quiet_hours_start ?? null,
      quiet_hours_end: quiet_hours_end ?? null,
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

  const { data, error } = await supabase
    .from("notification_rules")
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

  const { error } = await supabase
    .from("notification_rules")
    .delete()
    .eq("id", id);

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json({ success: true });
}
