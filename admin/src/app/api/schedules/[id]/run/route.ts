export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id) {
    return Response.json({ error: "id is required" }, { status: 400 });
  }

  // TODO: trigger actual digest run
  // For now, return success stub
  return Response.json({ success: true, schedule_id: id, message: "Run triggered" });
}
