"use client";

import { useEffect, useState, useCallback } from "react";
import type { Client, Company } from "@/lib/types";

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterCompany, setFilterCompany] = useState("");
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
    setCompanies(Array.isArray(data) ? data : []);
  }, []);

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Clients</h1>
        <select
          value={filterCompany}
          onChange={(e) => setFilterCompany(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">All Companies</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading...</div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">Name</th>
                <th className="px-5 py-3 font-medium text-slate-500">Email</th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  Organization
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  Status
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  Last Activity
                </th>
              </tr>
            </thead>
            <tbody>
              {clients.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-5 py-8 text-center text-slate-400"
                  >
                    No clients found
                  </td>
                </tr>
              ) : (
                clients.map((client) => (
                  <tr
                    key={client.id}
                    onClick={() => setSelectedClient(client)}
                    className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer"
                  >
                    <td className="px-5 py-3 font-medium text-slate-900">
                      {client.name ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {client.email}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {client.organization ?? "—"}
                    </td>
                    <td className="px-5 py-3">
                      <ClientStatusBadge status={client.status} />
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {client.last_activity_at
                        ? new Date(client.last_activity_at).toLocaleDateString()
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {selectedClient && (
        <ClientDetail
          client={selectedClient}
          onClose={() => setSelectedClient(null)}
        />
      )}
    </div>
  );
}

function ClientStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: "bg-emerald-50 text-emerald-700",
    lead: "bg-blue-50 text-blue-700",
    quoted: "bg-violet-50 text-violet-700",
    negotiating: "bg-amber-50 text-amber-700",
    closed: "bg-slate-100 text-slate-600",
    inactive: "bg-red-50 text-red-600",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status] ?? "bg-slate-100 text-slate-600"}`}
    >
      {status}
    </span>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            Client Details
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:text-slate-600"
          >
            &times;
          </button>
        </div>

        <div className="space-y-3">
          <Field label="Name" value={client.name} />
          <Field label="Email" value={client.email} />
          <Field label="Organization" value={client.organization} />
          <Field label="Phone" value={client.phone} />
          <Field label="Status" value={client.status} />
          <Field label="Notes" value={client.notes} />
          <Field
            label="First Seen"
            value={
              client.first_seen_at
                ? new Date(client.first_seen_at).toLocaleString()
                : null
            }
          />
          <Field
            label="Last Activity"
            value={
              client.last_activity_at
                ? new Date(client.last_activity_at).toLocaleString()
                : null
            }
          />
        </div>

        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="text-sm text-slate-800">{value ?? "—"}</p>
    </div>
  );
}
