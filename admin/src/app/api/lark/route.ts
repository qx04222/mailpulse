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

const LARK_TENANT_DOMAIN = "https://ajppbhsdfjyk.jp.larksuite.com";

export async function PATCH(request: Request) {
  const body = await request.json();
  const { action } = body as { action: string };

  if (action === "create_tabs") {
    const { chat_id, company_name, app_token, calendar_id } = body as {
      chat_id: string;
      company_name: string;
      app_token?: string;
      calendar_id?: string;
    };

    if (!chat_id) {
      return Response.json(
        { error: "chat_id is required" },
        { status: 400 }
      );
    }

    try {
      const token = await getLarkToken();
      const tabs: Array<{
        tab_name: string;
        tab_type: string;
        tab_content: { url: string };
      }> = [];

      if (app_token) {
        tabs.push({
          tab_name: `\u{1F4CA}邮件看板`,
          tab_type: "url",
          tab_content: {
            url: `${LARK_TENANT_DOMAIN}/base/${app_token}`,
          },
        });
      }

      if (calendar_id) {
        tabs.push({
          tab_name: `\u{1F4C5}跟进日历`,
          tab_type: "url",
          tab_content: {
            url: `${LARK_TENANT_DOMAIN}/calendar/${calendar_id}`,
          },
        });
      }

      if (tabs.length === 0) {
        return Response.json(
          { error: "No app_token or calendar_id provided" },
          { status: 400 }
        );
      }

      const resp = await fetch(
        `${LARK_BASE_URL}/open-apis/im/v1/chats/${chat_id}/chat_tabs`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ chat_tabs: tabs }),
        }
      );

      const data = await resp.json();
      if (data.code !== 0) {
        return Response.json(
          { error: data.msg || "Failed to create tabs" },
          { status: 500 }
        );
      }

      return Response.json({
        success: true,
        tabs_created: tabs.length,
        company: company_name,
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown error";
      return Response.json({ error: message }, { status: 500 });
    }
  }

  if (action === "sync_status") {
    const supabase = createAdminClient();

    try {
      const { data: baseRecords } = await supabase
        .from("lark_base_sync")
        .select("company_id, updated_at");

      const { data: calendarRecords } = await supabase
        .from("lark_calendar_events")
        .select("company_id");

      const stats: Record<
        string,
        {
          base_count: number;
          calendar_count: number;
          last_sync: string | null;
        }
      > = {};

      if (baseRecords) {
        for (const row of baseRecords) {
          if (!stats[row.company_id]) {
            stats[row.company_id] = {
              base_count: 0,
              calendar_count: 0,
              last_sync: null,
            };
          }
          stats[row.company_id].base_count += 1;
          const ts = row.updated_at as string;
          if (
            !stats[row.company_id].last_sync ||
            ts > stats[row.company_id].last_sync!
          ) {
            stats[row.company_id].last_sync = ts;
          }
        }
      }

      if (calendarRecords) {
        for (const row of calendarRecords) {
          if (!stats[row.company_id]) {
            stats[row.company_id] = {
              base_count: 0,
              calendar_count: 0,
              last_sync: null,
            };
          }
          stats[row.company_id].calendar_count += 1;
        }
      }

      return Response.json({ stats });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown error";
      return Response.json({ error: message }, { status: 500 });
    }
  }

  return Response.json({ error: "Unknown action" }, { status: 400 });
}
