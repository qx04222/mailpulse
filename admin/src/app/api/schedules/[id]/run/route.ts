import { createAdminClient } from "@/lib/supabase";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  const supabase = createAdminClient();

  // 查 schedule 获取 company_id
  const { data: schedule, error: schedError } = await supabase
    .from("digest_schedules")
    .select("id, company_id")
    .eq("id", id)
    .single();

  if (schedError || !schedule) {
    return Response.json({ error: "Schedule not found" }, { status: 404 });
  }

  // 写入 manual_triggers，engine 会自动消费
  const { error } = await supabase.from("manual_triggers").insert({
    schedule_id: schedule.id,
    company_id: schedule.company_id,
    status: "pending",
  });

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json({ success: true, message: "Run triggered, engine will process shortly." });
}
