import { createAdminClient } from "@/lib/supabase";
import { listAllUsers, listAllDepartments } from "@/lib/lark";

export async function POST() {
  try {
    const supabase = createAdminClient();
    const [larkUsers, larkDepts] = await Promise.all([
      listAllUsers(),
      listAllDepartments(),
    ]);

    // Build department name lookup
    const deptMap = new Map<string, string>();
    for (const d of larkDepts) {
      deptMap.set(d.department_id, d.name);
      deptMap.set(d.open_department_id, d.name);
    }

    // Get existing people to match by email or lark_user_id
    const { data: existing } = await supabase
      .from("people")
      .select("id, email, lark_user_id");

    const existingByEmail = new Map<string, string>();
    const existingByLark = new Map<string, string>();
    for (const p of existing ?? []) {
      if (p.email) existingByEmail.set(p.email.toLowerCase(), p.id);
      if (p.lark_user_id) existingByLark.set(p.lark_user_id, p.id);
    }

    let synced = 0;
    let created = 0;
    let updated = 0;

    for (const u of larkUsers) {
      const departments = u.department_ids
        ?.filter((id: string) => id !== "0")
        .map((id: string) => deptMap.get(id))
        .filter(Boolean) || [];

      const email = u.email || u.enterprise_email || "";
      const isActive = u.status?.is_activated && !u.status?.is_resigned && !u.status?.is_frozen;

      const updateData = {
        name: u.name,
        email,
        avatar_url: u.avatar?.avatar_240 || null,
        lark_user_id: u.open_id,
        is_active: isActive,
        person_type: "employee" as const,
        role: "member" as const,
        lark_departments: departments,
        lark_job_title: u.job_title || null,
        lark_mobile: u.mobile || null,
        lark_employee_no: u.employee_no || null,
        lark_synced_at: new Date().toISOString(),
      };

      // Match by lark_user_id first, then by email
      const existingId =
        existingByLark.get(u.open_id) ||
        (email ? existingByEmail.get(email.toLowerCase()) : null);

      if (existingId) {
        await supabase
          .from("people")
          .update(updateData)
          .eq("id", existingId);
        updated++;
      } else {
        await supabase
          .from("people")
          .insert(updateData);
        created++;
      }
      synced++;
    }

    return Response.json({
      success: true,
      synced,
      created,
      updated,
      total_lark_users: larkUsers.length,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("Lark sync error:", message);
    return Response.json({ error: message }, { status: 500 });
  }
}
