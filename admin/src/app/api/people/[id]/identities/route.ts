import { createAdminClient } from "@/lib/supabase";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: personId } = await params;
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("person_identities")
    .select("*")
    .eq("person_id", personId)
    .order("provider");

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: personId } = await params;
  const supabase = createAdminClient();
  const body = await request.json();
  const { provider, external_id, display_name, metadata } = body;

  if (!provider || !external_id) {
    return Response.json(
      { error: "provider and external_id are required" },
      { status: 400 }
    );
  }

  const { data, error } = await supabase
    .from("person_identities")
    .insert({
      person_id: personId,
      provider,
      external_id,
      display_name: display_name ?? null,
      metadata: metadata ?? {},
    })
    .select()
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json(data, { status: 201 });
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: personId } = await params;
  const supabase = createAdminClient();
  const { searchParams } = new URL(request.url);
  const identityId = searchParams.get("identity_id");

  if (!identityId) {
    return Response.json(
      { error: "identity_id is required" },
      { status: 400 }
    );
  }

  const { error } = await supabase
    .from("person_identities")
    .delete()
    .eq("id", identityId)
    .eq("person_id", personId);

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return Response.json({ success: true });
}
