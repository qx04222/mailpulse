import { createAdminClient } from "@/lib/supabase";

const LARK_BASE_URL = "https://open.larksuite.com";
const LARK_APP_ID = process.env.LARK_APP_ID || "";
const LARK_APP_SECRET = process.env.LARK_APP_SECRET || "";

async function getLarkToken(): Promise<string> {
  const resp = await fetch(
    `${LARK_BASE_URL}/open-apis/auth/v3/tenant_access_token/internal`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        app_id: LARK_APP_ID,
        app_secret: LARK_APP_SECRET,
      }),
    }
  );
  const data = await resp.json();
  if (data.code !== 0) {
    throw new Error(data.msg || "Failed to get Lark token");
  }
  return data.tenant_access_token;
}

export async function GET() {
  // Return Lark connection status + company group mappings
  const supabase = createAdminClient();

  const connected = !!(LARK_APP_ID && LARK_APP_SECRET);

  const { data: companies } = await supabase
    .from("companies")
    .select("id, name, lark_group_id, lark_base_app_token, lark_base_table_id, lark_calendar_id, is_active")
    .eq("is_active", true)
    .order("name");

  return Response.json({
    configured: connected,
    app_id: LARK_APP_ID ? LARK_APP_ID.substring(0, 8) + "..." : "",
    companies: companies || [],
  });
}

export async function POST() {
  // Test Lark API connection
  if (!LARK_APP_ID || !LARK_APP_SECRET) {
    return Response.json(
      {
        connected: false,
        error: "LARK_APP_ID or LARK_APP_SECRET not configured",
      },
      { status: 400 }
    );
  }

  try {
    const token = await getLarkToken();

    // Also fetch chat list to verify bot access
    const chatsResp = await fetch(
      `${LARK_BASE_URL}/open-apis/im/v1/chats?page_size=50`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      }
    );
    const chatsData = await chatsResp.json();
    const chats =
      chatsData.code === 0
        ? (chatsData.data?.items || []).map(
            (c: Record<string, unknown>) => ({
              chat_id: c.chat_id,
              name: c.name,
            })
          )
        : [];

    return Response.json({
      connected: true,
      token_preview: token.substring(0, 10) + "...",
      chat_count: chats.length,
      chats,
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return Response.json({ connected: false, error: message }, { status: 500 });
  }
}

export async function PUT(request: Request) {
  // Update company Lark group IDs
  const supabase = createAdminClient();
  const body = await request.json();
  const { companies } = body as {
    companies: Array<{
      id: string;
      lark_group_id: string | null;
      lark_base_app_token?: string | null;
      lark_base_table_id?: string | null;
      lark_calendar_id?: string | null;
    }>;
  };

  if (!companies || !Array.isArray(companies)) {
    return Response.json(
      { error: "companies array is required" },
      { status: 400 }
    );
  }

  const errors: string[] = [];
  for (const c of companies) {
    const { error } = await supabase
      .from("companies")
      .update({
        lark_group_id: c.lark_group_id || null,
        lark_base_app_token: c.lark_base_app_token || null,
        lark_base_table_id: c.lark_base_table_id || null,
        lark_calendar_id: c.lark_calendar_id || null,
      })
      .eq("id", c.id);

    if (error) {
      errors.push(`${c.id}: ${error.message}`);
    }
  }

  if (errors.length > 0) {
    return Response.json({ error: errors.join("; ") }, { status: 500 });
  }

  return Response.json({ success: true });
}
