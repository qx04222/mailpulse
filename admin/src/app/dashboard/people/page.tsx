"use client";

import { useEffect, useState, useCallback } from "react";
import { Download, Search, RefreshCw } from "lucide-react";

interface Person {
  id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  avatar_url: string | null;
  person_type: string;
  telegram_user_id: string | null;
  lark_user_id: string | null;
  lark_departments: string[];
  lark_job_title: string | null;
  lark_mobile: string | null;
  lark_employee_no: string | null;
  lark_synced_at: string | null;
  companies: { id: string; name: string }[];
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          active ? "bg-emerald-500" : "bg-slate-300"
        }`}
      />
      <span
        className={`text-xs font-medium ${
          active ? "text-emerald-700" : "text-slate-400"
        }`}
      >
        {active ? "Active" : "Inactive"}
      </span>
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  const styles: Record<string, string> = {
    owner: "bg-violet-100/80 text-violet-700",
    manager: "bg-blue-100/80 text-blue-700",
    member: "bg-slate-100 text-slate-500",
  };
  return (
    <span
      className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase ${
        styles[role] ?? "bg-slate-100 text-slate-500"
      }`}
    >
      {role}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    employee: "bg-blue-50 text-blue-700",
    shared_mailbox: "bg-amber-50 text-amber-700",
  };
  const labels: Record<string, string> = {
    employee: "Employee",
    shared_mailbox: "Shared",
  };
  return (
    <span
      className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase ${
        styles[type] ?? "bg-slate-100 text-slate-500"
      }`}
    >
      {labels[type] ?? type}
    </span>
  );
}

export default function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/people");
      if (!res.ok) throw new Error((await res.json()).error || "Failed to fetch");
      const data = await res.json();
      setPeople(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleSync() {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await fetch("/api/people/sync", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Sync failed");
      setSyncResult(
        `Synced: ${data.updated} updated, ${data.created} created`
      );
      fetchData();
    } catch (err) {
      setSyncResult(
        `Sync failed: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    } finally {
      setSyncing(false);
    }
  }

  const filtered = people.filter((p) => {
    if (filterType === "employee" && p.person_type !== "employee") return false;
    if (filterType === "shared_mailbox" && p.person_type !== "shared_mailbox")
      return false;
    if (filterType === "lark" && !p.lark_user_id) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      p.email?.toLowerCase().includes(q) ||
      p.lark_job_title?.toLowerCase().includes(q) ||
      p.lark_departments?.some((d) => d.toLowerCase().includes(q)) ||
      p.companies?.some((c) => c.name.toLowerCase().includes(q))
    );
  });

  const larkCount = people.filter((p) => p.lark_user_id).length;
  const activeCount = people.filter((p) => p.is_active).length;
  const lastSync = people
    .map((p) => p.lark_synced_at)
    .filter(Boolean)
    .sort()
    .pop();

  return (
    <div>
      {/* Hero Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-8 md:mb-12 gap-4">
        <div>
          <h1 className="text-3xl md:text-[2.75rem] font-bold tracking-tight text-on-surface leading-tight">
            Directory
          </h1>
          <p className="text-muted mt-2 max-w-xl text-sm md:text-base">
            Manage your organization&apos;s members, roles, and Lark
            integration from a centralized viewpoint.
          </p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-br from-primary to-primary-container text-on-primary font-medium rounded-xl shadow-lg shadow-primary/20 hover:shadow-xl hover:scale-[1.02] active:scale-95 transition-all disabled:opacity-60 disabled:pointer-events-none text-sm whitespace-nowrap"
        >
          <Download
            className={`h-4 w-4 ${syncing ? "animate-bounce" : ""}`}
          />
          <span>{syncing ? "Syncing..." : "Sync from Lark"}</span>
        </button>
      </div>

      {/* Sync result toast */}
      {syncResult && (
        <div
          className={`rounded-xl px-4 py-3 text-sm mb-6 ${
            syncResult.includes("failed")
              ? "bg-red-50 text-red-700"
              : "bg-emerald-50 text-emerald-700"
          }`}
        >
          {syncResult}
        </div>
      )}

      {/* Stats Bento */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 md:gap-6 mb-8">
        <div className="p-5 bg-surface-low rounded-2xl">
          <p className="text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-1.5">
            Total Members
          </p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-2xl font-bold text-on-surface">
              {people.length}
            </h3>
            <span className="text-xs text-muted font-medium">
              {activeCount} active
            </span>
          </div>
        </div>
        <div className="p-5 bg-surface-low rounded-2xl">
          <p className="text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-1.5">
            Lark Connected
          </p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-2xl font-bold text-on-surface">{larkCount}</h3>
            <span className="text-xs text-muted font-medium">
              of {people.length}
            </span>
          </div>
          <div className="mt-3 h-1.5 w-full bg-surface-high rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-container rounded-full transition-all"
              style={{
                width: `${people.length > 0 ? (larkCount / people.length) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
        <div className="p-5 bg-primary text-on-primary rounded-2xl relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-transparent" />
          <p className="text-[11px] font-bold uppercase tracking-widest text-white/70 mb-1.5 relative z-10">
            Sync Status
          </p>
          <div className="flex items-center gap-2 relative z-10">
            <h3 className="text-2xl font-bold">
              {lastSync ? "Healthy" : "Not synced"}
            </h3>
            {lastSync && <RefreshCw className="h-4 w-4 text-white/50" />}
          </div>
          <p className="text-xs text-white/60 mt-3 relative z-10">
            {lastSync
              ? `Last sync: ${new Date(lastSync).toLocaleString("zh-CN")}`
              : "Click 'Sync from Lark' to start"}
          </p>
        </div>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search members, roles or departments..."
            className="w-full bg-surface-low border-none rounded-xl py-2.5 pl-10 pr-4 text-sm focus:ring-2 focus:ring-primary-container/20 transition-all outline-none placeholder:text-slate-400"
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="rounded-xl bg-surface-low border-none px-4 py-2.5 text-sm text-muted focus:ring-2 focus:ring-primary-container/20 outline-none"
        >
          <option value="all">All types</option>
          <option value="employee">Employees</option>
          <option value="shared_mailbox">Shared Mailbox</option>
          <option value="lark">Lark Connected</option>
        </select>
      </div>

      {error && (
        <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 mb-6">
          {error}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="text-center py-16 text-muted">Loading...</div>
      ) : (
        <div className="bg-surface-card rounded-2xl overflow-hidden shadow-[0px_20px_40px_rgba(25,28,30,0.04)]">
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-low">
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Name
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Email
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Type
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Role
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Department
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Status
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Lark
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-8 py-16 text-center text-muted"
                    >
                      {search ? "No matching results" : "No members found"}
                    </td>
                  </tr>
                ) : (
                  filtered.map((person) => (
                    <tr
                      key={person.id}
                      className="group hover:bg-surface-low transition-colors duration-200"
                    >
                      <td className="px-6 lg:px-8 py-4">
                        <div className="flex items-center gap-3">
                          {person.avatar_url ? (
                            <img
                              src={person.avatar_url}
                              alt={person.name}
                              className="w-9 h-9 rounded-full bg-slate-100 border-2 border-white shadow-sm object-cover"
                            />
                          ) : (
                            <div className="w-9 h-9 rounded-full bg-primary-container/10 border-2 border-white shadow-sm flex items-center justify-center text-xs font-bold text-primary-container">
                              {person.name.charAt(0)}
                            </div>
                          )}
                          <div>
                            <p className="text-sm font-semibold text-on-surface">
                              {person.name}
                            </p>
                            {person.lark_job_title && (
                              <p className="text-[11px] text-muted/60">
                                {person.lark_job_title}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        <span className="text-sm text-muted font-medium">
                          {person.email || "\u2014"}
                        </span>
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        <TypeBadge type={person.person_type} />
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        <RoleBadge role={person.role} />
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        {person.lark_departments?.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {person.lark_departments.map((dept, i) => (
                              <span
                                key={i}
                                className="px-2 py-0.5 rounded-full bg-blue-50 text-[11px] font-medium text-blue-700"
                              >
                                {dept}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-muted/40">{"\u2014"}</span>
                        )}
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        <StatusDot active={person.is_active} />
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        {person.lark_user_id ? (
                          <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-[11px] font-bold text-emerald-700">
                            Connected
                          </span>
                        ) : (
                          <span className="text-muted/40 text-xs">
                            {"\u2014"}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden divide-y divide-slate-100">
            {filtered.length === 0 ? (
              <div className="px-4 py-12 text-center text-muted text-sm">
                {search ? "No matching results" : "No members found"}
              </div>
            ) : (
              filtered.map((person) => (
                <div key={person.id} className="px-4 py-4 space-y-2.5">
                  <div className="flex items-center gap-3">
                    {person.avatar_url ? (
                      <img
                        src={person.avatar_url}
                        alt={person.name}
                        className="w-10 h-10 rounded-full bg-slate-100 border-2 border-white shadow-sm object-cover"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-primary-container/10 border-2 border-white shadow-sm flex items-center justify-center text-sm font-bold text-primary-container">
                        {person.name.charAt(0)}
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-on-surface truncate">
                          {person.name}
                        </p>
                        <StatusDot active={person.is_active} />
                      </div>
                      <p className="text-xs text-muted truncate">
                        {person.email || "\u2014"}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 pl-[52px]">
                    <TypeBadge type={person.person_type} />
                    <RoleBadge role={person.role} />
                    {person.lark_user_id && (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-[11px] font-bold text-emerald-700">
                        Lark
                      </span>
                    )}
                  </div>
                  {person.lark_departments?.length > 0 && (
                    <div className="flex flex-wrap gap-1 pl-[52px]">
                      {person.lark_departments.map((dept, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded-full bg-blue-50 text-[11px] font-medium text-blue-700"
                        >
                          {dept}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-4 md:px-8 py-4 bg-surface-card flex items-center justify-between border-t border-slate-100">
            <p className="text-[11px] font-bold uppercase tracking-widest text-muted/60">
              Showing {filtered.length} of {people.length} members
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
