const LARK_BASE = "https://open.larksuite.com/open-apis";

let cachedToken: { token: string; expiresAt: number } | null = null;

export async function getTenantAccessToken(): Promise<string> {
  if (cachedToken && Date.now() < cachedToken.expiresAt) {
    return cachedToken.token;
  }

  const res = await fetch(`${LARK_BASE}/auth/v3/tenant_access_token/internal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      app_id: process.env.LARK_APP_ID,
      app_secret: process.env.LARK_APP_SECRET,
    }),
  });

  const data = await res.json();
  if (data.code !== 0) {
    throw new Error(`Lark auth failed: ${data.msg}`);
  }

  cachedToken = {
    token: data.tenant_access_token,
    expiresAt: Date.now() + (data.expire - 60) * 1000, // refresh 60s early
  };

  return cachedToken.token;
}

async function larkGet(path: string, params?: Record<string, string>) {
  const token = await getTenantAccessToken();
  const url = new URL(`${LARK_BASE}${path}`);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, v);
    }
  }

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await res.json();
  if (data.code !== 0) {
    throw new Error(`Lark API error [${path}]: ${data.msg}`);
  }
  return data.data;
}

export interface LarkUser {
  user_id: string;
  open_id: string;
  name: string;
  en_name: string;
  nickname: string;
  email: string;
  mobile: string;
  mobile_visible: boolean;
  avatar: {
    avatar_72: string;
    avatar_240: string;
    avatar_640: string;
    avatar_origin: string;
  };
  status: {
    is_frozen: boolean;
    is_resigned: boolean;
    is_activated: boolean;
    is_exited: boolean;
    is_unjoin: boolean;
  };
  department_ids: string[];
  leader_user_id: string;
  city: string;
  country: string;
  work_station: string;
  join_time: number;
  employee_no: string;
  employee_type: number;
  job_title: string;
  enterprise_email: string;
  gender: number; // 0=unknown, 1=male, 2=female
}

export interface LarkDepartment {
  department_id: string;
  name: string;
  parent_department_id: string;
  open_department_id: string;
  leader_user_id: string;
  member_count: number;
  status: { is_deleted: boolean };
}

/** Fetch all users across all pages */
export async function listAllUsers(): Promise<LarkUser[]> {
  const users: LarkUser[] = [];
  let pageToken: string | undefined;

  do {
    const params: Record<string, string> = {
      page_size: "50",
      department_id: "0", // root department = all
    };
    if (pageToken) params.page_token = pageToken;

    const data = await larkGet("/contact/v3/users", params);
    if (data.items) {
      users.push(...data.items);
    }
    pageToken = data.has_more ? data.page_token : undefined;
  } while (pageToken);

  return users;
}

/** Fetch all departments */
export async function listAllDepartments(): Promise<LarkDepartment[]> {
  const departments: LarkDepartment[] = [];
  let pageToken: string | undefined;

  do {
    const params: Record<string, string> = {
      page_size: "50",
      parent_department_id: "0",
      fetch_child: "true",
    };
    if (pageToken) params.page_token = pageToken;

    const data = await larkGet("/contact/v3/departments", params);
    if (data.items) {
      departments.push(...data.items);
    }
    pageToken = data.has_more ? data.page_token : undefined;
  } while (pageToken);

  return departments;
}

/** Get a single user by user_id */
export async function getUser(userId: string): Promise<LarkUser> {
  const data = await larkGet(`/contact/v3/users/${userId}`, {
    user_id_type: "user_id",
  });
  return data.user;
}
