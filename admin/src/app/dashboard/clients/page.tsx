"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, X } from "lucide-react";

interface Company {
  id: string;
  name: string;
}

interface Client {
  id: string;
  email: string;
  name: string | null;
  organization: string | null;
  phone: string | null;
  status: string;
  notes: string | null;
  first_seen_at: string;
  last_activity_at: string;
  companies: Company[];
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-emerald-500",
  lead: "bg-blue-500",
  quoted: "bg-violet-500",
  negotiating: "bg-amber-400",
  closed: "bg-slate-400",
  inactive: "bg-red-400",
};

const STATUS_TEXT: Record<string, string> = {
  active: "text-emerald-700",
  lead: "text-blue-700",
  quoted: "text-violet-700",
  negotiating: "text-amber-700",
  closed: "text-slate-500",
  inactive: "text-red-600",
};

function StatusDot({ status }: { status: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`w-1.5 h-1.5 rounded-full ${STATUS_STYLES[status] ?? "bg-slate-300"}`}
      />
      <span
        className={`text-xs font-medium capitalize ${STATUS_TEXT[status] ?? "text-slate-500"}`}
      >
        {status}
      </span>
    </div>
  );
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [allCompanies, setAllCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterCompany, setFilterCompany] = useState("");
  const [search, setSearch] = useState("");
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    const params = filterCompany ? `?company_id=${filterCompany}` : "";
    const res = await fetch(`/api/clients${params}`);
    const data = await res.json();
    setClients(Array.isArray(data) ? data : []);
    setLoading(false);
  }, [filterCompany]);

  const fetchCompanies = useCallback(async () => {
    const res = await fetch("/api/companies");
    const data = await res.json();
    setAllCompanies(Array.isArray(data) ? data : []);
  }, []);

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  const filtered = clients.filter((c) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      c.name?.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.organization?.toLowerCase().includes(q) ||
      c.companies?.some((co) => co.name.toLowerCase().includes(q))
    );
  });

  // Count per company
  const companyCounts = new Map<string, number>();
  for (const c of clients) {
    for (const co of c.companies ?? []) {
      companyCounts.set(co.name, (companyCounts.get(co.name) ?? 0) + 1);
    }
  }

  return (
    <div>
      {/* Hero Header */}
      <div className="mb-8 md:mb-12">
        <h1 className="text-3xl md:text-[2.75rem] font-bold tracking-tight text-on-surface leading-tight">
          Clients
        </h1>
        <p className="text-muted mt-2 max-w-xl text-sm md:text-base">
          All client contacts discovered from email threads, organized by
          company.
        </p>
      </div>

      {/* Company stats */}
      <div className="flex flex-wrap gap-3 mb-8">
        <button
          onClick={() => setFilterCompany("")}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
            filterCompany === ""
              ? "bg-primary text-on-primary shadow-lg shadow-primary/20"
              : "bg-surface-low text-muted hover:bg-surface-high"
          }`}
        >
          All ({clients.length})
        </button>
        {allCompanies.map((co) => (
          <button
            key={co.id}
            onClick={() =>
              setFilterCompany(filterCompany === co.id ? "" : co.id)
            }
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filterCompany === co.id
                ? "bg-primary text-on-primary shadow-lg shadow-primary/20"
                : "bg-surface-low text-muted hover:bg-surface-high"
            }`}
          >
            {co.name}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search clients, emails, organizations, companies..."
          className="w-full bg-surface-low border-none rounded-xl py-2.5 pl-10 pr-4 text-sm focus:ring-2 focus:ring-primary-container/20 transition-all outline-none placeholder:text-slate-400"
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-16 text-muted">Loading...</div>
      ) : (
        <div className="bg-surface-card rounded-2xl overflow-hidden shadow-[0px_20px_40px_rgba(25,28,30,0.04)]">
          {/* Desktop */}
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
                    Organization
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Companies
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Status
                  </th>
                  <th className="px-6 lg:px-8 py-4 text-[11px] font-bold uppercase tracking-widest text-muted/70 border-b border-outline-dim/10">
                    Last Activity
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-8 py-16 text-center text-muted"
                    >
                      No clients found
                    </td>
                  </tr>
                ) : (
                  filtered.map((client) => (
                    <tr
                      key={client.id}
                      onClick={() => setSelectedClient(client)}
                      className="group hover:bg-surface-low transition-colors duration-200 cursor-pointer"
                    >
                      <td className="px-6 lg:px-8 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-primary-container/10 border-2 border-white shadow-sm flex items-center justify-center text-xs font-bold text-primary-container">
                            {(client.name ?? client.email).charAt(0).toUpperCase()}
                          </div>
                          <p className="text-sm font-semibold text-on-surface">
                            {client.name ?? "\u2014"}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        <span className="text-sm text-muted font-medium">
                          {client.email}
                        </span>
                      </td>
                      <td className="px-6 lg:px-8 py-4 text-sm text-muted">
                        {client.organization ?? "\u2014"}
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        {client.companies?.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {client.companies.map((co) => (
                              <span
                                key={co.id}
                                className="px-2 py-0.5 rounded-full bg-blue-50 text-[11px] font-medium text-blue-700"
                              >
                                {co.name}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-muted/40">{"\u2014"}</span>
                        )}
                      </td>
                      <td className="px-6 lg:px-8 py-4">
                        <StatusDot status={client.status} />
                      </td>
                      <td className="px-6 lg:px-8 py-4 text-sm text-muted">
                        {client.last_activity_at
                          ? new Date(
                              client.last_activity_at
                            ).toLocaleDateString("zh-CN")
                          : "\u2014"}
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
                No clients found
              </div>
            ) : (
              filtered.map((client) => (
                <div
                  key={client.id}
                  onClick={() => setSelectedClient(client)}
                  className="px-4 py-4 space-y-2 cursor-pointer active:bg-surface-low"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary-container/10 border-2 border-white shadow-sm flex items-center justify-center text-sm font-bold text-primary-container">
                      {(client.name ?? client.email)
                        .charAt(0)
                        .toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-on-surface truncate">
                          {client.name ?? client.email}
                        </p>
                        <StatusDot status={client.status} />
                      </div>
                      <p className="text-xs text-muted truncate">
                        {client.email}
                      </p>
                    </div>
                  </div>
                  {client.companies?.length > 0 && (
                    <div className="flex flex-wrap gap-1 pl-[52px]">
                      {client.companies.map((co) => (
                        <span
                          key={co.id}
                          className="px-2 py-0.5 rounded-full bg-blue-50 text-[11px] font-medium text-blue-700"
                        >
                          {co.name}
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
              Showing {filtered.length} of {clients.length} clients
            </p>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedClient && (
        <ClientDetail
          client={selectedClient}
          onClose={() => setSelectedClient(null)}
        />
      )}
    </div>
  );
}

function ClientDetail({
  client,
  onClose,
}: {
  client: Client;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-surface-card p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold tracking-tight text-on-surface">
            Client Details
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted hover:bg-surface-low"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4">
          <Field label="Name" value={client.name} />
          <Field label="Email" value={client.email} />
          <Field label="Organization" value={client.organization} />
          <Field label="Phone" value={client.phone} />
          <div>
            <p className="text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-1">
              Companies
            </p>
            {client.companies?.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {client.companies.map((co) => (
                  <span
                    key={co.id}
                    className="px-2.5 py-1 rounded-full bg-blue-50 text-xs font-medium text-blue-700"
                  >
                    {co.name}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">{"\u2014"}</p>
            )}
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-1">
              Status
            </p>
            <StatusDot status={client.status} />
          </div>
          <Field label="Notes" value={client.notes} />
          <Field
            label="First Seen"
            value={
              client.first_seen_at
                ? new Date(client.first_seen_at).toLocaleString("zh-CN")
                : null
            }
          />
          <Field
            label="Last Activity"
            value={
              client.last_activity_at
                ? new Date(client.last_activity_at).toLocaleString("zh-CN")
                : null
            }
          />
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div>
      <p className="text-[11px] font-bold uppercase tracking-widest text-muted/60 mb-1">
        {label}
      </p>
      <p className="text-sm text-on-surface">{value ?? "\u2014"}</p>
    </div>
  );
}
