export interface PersonIdentity {
  id: string;
  person_id: string;
  provider: string;
  external_id: string;
  display_name: string | null;
  metadata: Record<string, unknown>;
  is_verified: boolean;
  created_at: string;
}

export interface Person {
  id: string;
  name: string;
  email: string;
  telegram_user_id: string | null;
  role: "owner" | "manager" | "member";
  is_active: boolean;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
  companies?: Company[];
  identities?: PersonIdentity[];
}

export interface Company {
  id: string;
  name: string;
  gmail_label: string;
  telegram_group_id: string | null;
  logo_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  members?: Person[];
}

export interface Client {
  id: string;
  email: string;
  name: string | null;
  organization: string | null;
  phone: string | null;
  status: "lead" | "active" | "quoted" | "negotiating" | "closed" | "inactive";
  notes: string | null;
  first_seen_at: string;
  last_activity_at: string;
  created_at: string;
}

export interface Thread {
  id: string;
  gmail_thread_id: string;
  company_id: string;
  subject: string | null;
  status: "active" | "waiting_reply" | "resolved" | "stale";
  initiated_by: "us" | "them" | null;
  email_count: number;
  inbound_count: number;
  outbound_count: number;
  first_email_at: string | null;
  last_email_at: string | null;
  client?: Client;
  company?: Company;
}

export interface ActionItem {
  id: string;
  company_id: string;
  title: string;
  description: string | null;
  priority: "high" | "medium" | "low";
  status: "pending" | "in_progress" | "overdue" | "resolved" | "dismissed";
  assigned_to_id: string | null;
  due_date: string | null;
  seen_count: number;
  created_at: string;
  updated_at: string;
  company?: Company;
  assigned_to?: Person;
  client?: Client;
}

export interface DigestRun {
  id: string;
  company_id: string;
  run_date: string;
  total_emails: number;
  new_emails: number;
  high_priority: number;
  action_items_created: number;
  telegram_delivered: boolean;
  report_docx_url: string | null;
  report_pdf_url: string | null;
  status: "running" | "completed" | "failed";
  started_at: string;
  completed_at: string | null;
  company?: Company;
}
