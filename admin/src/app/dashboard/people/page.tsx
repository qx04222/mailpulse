"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Download,
  Search,
  RefreshCw,
  X,
  Plus,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";

/* ────────────────────────────── Types ────────────────────────────── */

interface PersonIdentity {
  id: string;
  person_id: string;
  provider: string;
  external_id: string;
  display_name: string | null;
  metadata: Record<string, unknown>;
  is_verified: boolean;
  created_at: string;
}

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
  identities: PersonIdentity[];
}

/* ────────────────────────────── Provider config ────────────────────────────── */

const PROVIDER_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; dot: string }
> = {
  gmail: {
    label: "Gmail",
    bg: "bg-red-100/80",
    text: "text-red-700",
    dot: "bg-red-500",
  },
  lark: {
    label: "Lark",
    bg: "bg-blue-100/80",
    text: "text-blue-700",
    dot: "bg-blue-500",
  },
  zoho: {
    label: "Zoho",
    bg: "bg-purple-100/80",
    text: "text-purple-700",
    dot: "bg-purple-500",
  },
  arcview_saas: {
    label: "Arcview SaaS",
    bg: "bg-emerald-100/80",
    text: "text-emerald-700",
    dot: "bg-emerald-500",
  },
  arcnexus_saas: {
    label: "ArcNexus SaaS",
    bg: "bg-amber-100/80",
    text: "text-amber-700",
    dot: "bg-amber-500",
  },
  torquemax_saas: {
    label: "TorqueMax SaaS",
    bg: "bg-orange-100/80",
    text: "text-orange-700",
    dot: "bg-orange-500",
  },
  telegram: {
    label: "Telegram",
    bg: "bg-sky-100/80",
    text: "text-sky-700",
    dot: "bg-sky-500",
  },
};

function getProviderStyle(provider: string) {
  return (
    PROVIDER_CONFIG[provider] ?? {
      label: provider,
      bg: "bg-slate-100",
      text: "text-slate-600",
      dot: "bg-slate-400",
    }
  );
}

const PROVIDER_OPTIONS = [
  "gmail",
  "lark",
  "zoho",
  "arcview_saas",
  "arcnexus_saas",
  "torquemax_saas",
  "telegram",
  "other",
];

/* ────────────────────────────── Small components ────────────────────────────── */

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

function ProviderBadge({
  provider,
  compact,
}: {
  provider: string;
  compact?: boolean;
}) {
  const style = getProviderStyle(provider);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-bold tracking-wide uppercase ${
        style.bg
      } ${style.text} ${
        compact
          ? "px-2 py-0.5 text-[10px]"
          : "px-2.5 py-0.5 text-[11px]"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}

/* ────────────────────────────── Identity Row ────────────────────────────── */

function IdentityRow({
  identity,
  onDelete,
  deleting,
}: {
  identity: PersonIdentity;
  onDelete: (id: string) => void;
  deleting: boolean;
}) {
  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-xl bg-surface-low group hover:bg-slate-50 transition-colors">
      <ProviderBadge provider={identity.provider} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-on-surface truncate">
          {identity.external_id}
        </p>
        {identity.display_name && (
          <p className="text-[11px] text-muted/60 truncate">
            {identity.display_name}
          </p>
        )}
      </div>
      {identity.is_verified && (
        <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0" />
      )}
      <button
        onClick={() => onDelete(identity.id)}
        disabled={deleting}
        className="rounded-lg p-1.5 text-slate-300 hover:bg-red-50 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-50"
        title="Remove identity"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/* ────────────────────────────── Add Identity Form ────────────────────────────── */

function AddIdentityForm({
  personId,
  onSaved,
  onCancel,
}: {
  personId: string;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [provider, setProvider] = useState("gmail");
  const [externalId, setExternalId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!externalId.trim()) return;
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`/api/people/${personId}/identities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          external_id: externalId.trim(),
          display_name: displayName.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to add identity");
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-3 p-3 rounded-xl bg-surface-low border border-dashed border-slate-200 space-y-3"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-1">
            Provider
          </label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="w-full rounded-lg bg-white border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-primary-container/20 outline-none"
          >
            {PROVIDER_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {getProviderStyle(p).label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-1">
            External ID
          </label>
          <input
            type="text"
            value={externalId}
            onChange={(e) => setExternalId(e.target.value)}
            placeholder="email@example.com"
            className="w-full rounded-lg bg-white border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-primary-container/20 outline-none placeholder:text-slate-400"
            required
          />
        </div>
      </div>
      <div>
        <label className="block text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-1">
          Display Name (optional)
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Alternative display name"
          className="w-full rounded-lg bg-white border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-primary-container/20 outline-none placeholder:text-slate-400"
        />
      </div>
      {error && (
        <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          {error}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 rounded-lg text-sm font-medium text-muted hover:bg-slate-100 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving || !externalId.trim()}
          className="px-4 py-1.5 rounded-lg bg-primary text-on-primary text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </form>
  );
}

/* ────────────────────────────── Person Detail Panel (Slide-over) ────────────────────────────── */

function PersonDetailPanel({
  person,
  onClose,
  onIdentityChanged,
}: {
  person: Person;
  onClose: () => void;
  onIdentityChanged: () => void;
}) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function handleDeleteIdentity(identityId: string) {
    setDeletingId(identityId);
    try {
      const res = await fetch(
        `/api/people/${person.id}/identities?identity_id=${identityId}`,
        { method: "DELETE" }
      );
      if (!res.ok) {
        const data = await res.json();
        alert(data.error || "Failed to remove identity");
      }
      onIdentityChanged();
    } catch {
      alert("Failed to remove identity");
    } finally {
      setDeletingId(null);
    }
  }

  const identities = person.identities ?? [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative w-full max-w-lg bg-white shadow-2xl overflow-y-auto animate-in slide-in-from-right">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-white/90 backdrop-blur-md border-b border-slate-100 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-on-surface">Person Details</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted hover:bg-surface-low hover:text-on-surface transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-6 space-y-8">
          {/* Section 1: Person Info */}
          <div>
            <h3 className="text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-4">
              Person Info
            </h3>
            <div className="flex items-start gap-4">
              {person.avatar_url ? (
                <img
                  src={person.avatar_url}
                  alt={person.name}
                  className="w-14 h-14 rounded-2xl bg-slate-100 border-2 border-white shadow-md object-cover shrink-0"
                />
              ) : (
                <div className="w-14 h-14 rounded-2xl bg-primary-container/10 border-2 border-white shadow-md flex items-center justify-center text-lg font-bold text-primary-container shrink-0">
                  {person.name.charAt(0)}
                </div>
              )}
              <div className="flex-1 min-w-0 space-y-1.5">
                <p className="text-xl font-bold text-on-surface leading-tight">
                  {person.name}
                </p>
                {person.email && (
                  <p className="text-sm text-muted truncate">{person.email}</p>
                )}
                {person.lark_job_title && (
                  <p className="text-xs text-muted/60">
                    {person.lark_job_title}
                  </p>
                )}
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <TypeBadge type={person.person_type} />
              <RoleBadge role={person.role} />
              <StatusDot active={person.is_active} />
            </div>

            {person.lark_departments?.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {person.lark_departments.map((dept, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-0.5 rounded-full bg-blue-50 text-[11px] font-medium text-blue-700"
                  >
                    {dept}
                  </span>
                ))}
              </div>
            )}

            {person.lark_user_id && (
              <div className="mt-3 flex items-center gap-2 text-xs text-muted/60">
                <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-bold text-[11px]">
                  Lark Connected
                </span>
                {person.lark_employee_no && (
                  <span>No. {person.lark_employee_no}</span>
                )}
                {person.lark_mobile && <span>{person.lark_mobile}</span>}
              </div>
            )}
          </div>

          {/* Section 2: Connected Identities */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-muted/60">
                Connected Identities
              </h3>
              <span className="text-xs text-muted font-medium">
                {identities.length} connected
              </span>
            </div>

            {identities.length === 0 && !showAddForm ? (
              <div className="py-6 text-center text-sm text-muted/50 bg-surface-low rounded-xl">
                No identities connected yet
              </div>
            ) : (
              <div className="space-y-2">
                {identities.map((identity) => (
                  <IdentityRow
                    key={identity.id}
                    identity={identity}
                    onDelete={handleDeleteIdentity}
                    deleting={deletingId === identity.id}
                  />
                ))}
              </div>
            )}

            {showAddForm ? (
              <AddIdentityForm
                personId={person.id}
                onSaved={() => {
                  setShowAddForm(false);
                  onIdentityChanged();
                }}
                onCancel={() => setShowAddForm(false)}
              />
            ) : (
              <button
                onClick={() => setShowAddForm(true)}
                className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-dashed border-slate-200 text-sm font-medium text-muted hover:bg-surface-low hover:border-primary-container/30 hover:text-primary-container transition-all"
              >
                <Plus className="h-4 w-4" />
                Add Identity
              </button>
            )}
          </div>

          {/* Section 3: Companies */}
          <div>
            <h3 className="text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-3">
              Companies
            </h3>
            {person.companies?.length > 0 ? (
              <div className="space-y-2">
                {person.companies.map((company) => (
                  <div
                    key={company.id}
                    className="flex items-center gap-3 py-2.5 px-3 rounded-xl bg-surface-low"
                  >
                    <div className="w-8 h-8 rounded-lg bg-primary-container/10 flex items-center justify-center text-xs font-bold text-primary-container">
                      {company.name.charAt(0)}
                    </div>
                    <span className="text-sm font-medium text-on-surface">
                      {company.name}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-sm text-muted/50 bg-surface-low rounded-xl">
                Not associated with any company
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────── Main Page ────────────────────────────── */

export default function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/people");
      if (!res.ok)
        throw new Error((await res.json()).error || "Failed to fetch");
      const data = await res.json();
      const list: Person[] = (Array.isArray(data) ? data : []).map(
        (p: Person) => ({
          ...p,
          identities: p.identities ?? [],
          companies: p.companies ?? [],
        })
      );
      setPeople(list);

      // Keep selected person in sync after refetch
      if (selectedPerson) {
        const updated = list.find((p) => p.id === selectedPerson.id);
        if (updated) setSelectedPerson(updated);
        else setSelectedPerson(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  function handleIdentityChanged() {
    fetchData();
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
      p.companies?.some((c) => c.name.toLowerCase().includes(q)) ||
      p.identities?.some(
        (id) =>
          id.external_id.toLowerCase().includes(q) ||
          id.provider.toLowerCase().includes(q)
      )
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
            Manage your organization&apos;s members, roles, and connected
            identities from a centralized viewpoint.
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
            placeholder="Search members, identities or departments..."
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
                    Identities
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
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10 w-10" />
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
                      onClick={() => setSelectedPerson(person)}
                      className="group hover:bg-surface-low transition-colors duration-200 cursor-pointer"
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
                        {person.identities.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {person.identities.map((id) => (
                              <ProviderBadge
                                key={id.id}
                                provider={id.provider}
                                compact
                              />
                            ))}
                          </div>
                        ) : (
                          <span className="text-muted/40 text-xs">
                            {"\u2014"}
                          </span>
                        )}
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
                      <td className="px-4 py-4">
                        <ChevronRight className="h-4 w-4 text-muted/30 group-hover:text-muted/60 transition-colors" />
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
                <div
                  key={person.id}
                  onClick={() => setSelectedPerson(person)}
                  className="px-4 py-4 space-y-2.5 cursor-pointer active:bg-surface-low transition-colors"
                >
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
                    <ChevronRight className="h-4 w-4 text-muted/30 shrink-0" />
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 pl-[52px]">
                    <TypeBadge type={person.person_type} />
                    <RoleBadge role={person.role} />
                    {person.identities.length > 0 &&
                      person.identities.map((id) => (
                        <ProviderBadge
                          key={id.id}
                          provider={id.provider}
                          compact
                        />
                      ))}
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

      {/* Person Detail Slide-over */}
      {selectedPerson && (
        <PersonDetailPanel
          person={selectedPerson}
          onClose={() => setSelectedPerson(null)}
          onIdentityChanged={handleIdentityChanged}
        />
      )}
    </div>
  );
}
