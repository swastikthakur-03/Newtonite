"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useRequireAuth, useAuth } from "@/lib/auth-context";
import { getTeamsApi, getTeamMembersApi, createWorkItemApi } from "@/lib/api";
import { ArrowLeft, PlusCircle, AlertCircle, ShieldCheck } from "lucide-react";
import { ApiError } from "@/types";

function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export default function NewWorkItemPage() {
  const router = useRouter();
  const { user } = useRequireAuth();
  const { isGlobalAdmin, hasRoleInTeam } = useAuth();

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [teamId, setTeamId] = useState<number | undefined>(undefined);
  const [priority, setPriority] = useState<string>("MEDIUM");
  const [assigneeId, setAssigneeId] = useState<number | undefined>(undefined);
  const [dueDate, setDueDate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  // Client-side generated idempotency key for this creation session
  const [idempotencyKey, setIdempotencyKey] = useState<string>("");

  useEffect(() => {
    setIdempotencyKey(generateUUID());
  }, []);

  // Fetch teams accessible to user
  const { data: teams, isLoading: teamsLoading } = useQuery({
    queryKey: ["teams"],
    queryFn: getTeamsApi,
    enabled: !!user,
  });

  // Set default team once teams load
  useEffect(() => {
    if (teams && teams.length > 0 && !teamId) {
      setTeamId(teams[0].id);
    }
  }, [teams, teamId]);

  // Fetch members for the selected team to populate assignee dropdown
  const { data: members } = useQuery({
    queryKey: ["team-members", teamId],
    queryFn: () => (teamId ? getTeamMembersApi(teamId) : Promise.resolve([])),
    enabled: !!teamId,
  });

  const canAssignOthers = teamId ? hasRoleInTeam(teamId, ["MANAGER", "ADMIN"]) : false;

  const createMutation = useMutation({
    mutationFn: () =>
      createWorkItemApi(
        {
          title: title.trim(),
          description: description.trim() || undefined,
          priority,
          team_id: teamId!,
          assignee_id: assigneeId,
          due_date: dueDate ? new Date(dueDate).toISOString() : undefined,
        },
        idempotencyKey // Pass client idempotency key
      ),
    onSuccess: (newItem) => {
      router.push(`/work-items/${newItem.id}`);
    },
    onError: (err: ApiError) => {
      setError(err?.message || "Failed to create work item.");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    if (!teamId) {
      setError("Please select a team.");
      return;
    }
    createMutation.mutate();
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <Link
          href="/work-items"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Work Items
        </Link>
      </div>

      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm space-y-5">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Create New Work Item</h1>
          <p className="text-xs text-gray-500 mt-1">
            Initiate a trackable operational task, customer issue, or incident investigation.
          </p>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-red-700 text-sm">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g., Payment Gateway Error Rate Anomaly"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Description / Context</label>
            <textarea
              rows={4}
              placeholder="Describe what occurred, customer impact, steps taken, or initial findings..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Target Team <span className="text-red-500">*</span>
              </label>
              <select
                value={teamId || ""}
                onChange={(e) => {
                  setTeamId(Number(e.target.value));
                  setAssigneeId(undefined); // reset assignee on team change
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {teamsLoading && <option>Loading teams...</option>}
                {teams?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium (Default)</option>
                <option value="HIGH">High</option>
                <option value="URGENT">Urgent (Immediate attention)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Initial Assignee {canAssignOthers ? "(Optional)" : "(Leave unassigned or claim later)"}
              </label>
              <select
                value={assigneeId || ""}
                onChange={(e) => setAssigneeId(e.target.value ? Number(e.target.value) : undefined)}
                disabled={!canAssignOthers}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white disabled:bg-gray-100 disabled:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Leave Unassigned</option>
                {members?.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.user_name} ({m.role})
                  </option>
                ))}
              </select>
              {!canAssignOthers && (
                <span className="text-[11px] text-gray-400 mt-0.5 block">
                  Only Managers or Admins can assign on creation.
                </span>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Due Date (Optional)</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Idempotency Key Info Notice */}
          <div className="pt-2 flex items-center justify-between text-[11px] text-gray-400 border-t border-gray-100">
            <span className="flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              Protected by Idempotency Key:
            </span>
            <span className="font-mono text-gray-500">{idempotencyKey.slice(0, 8)}...</span>
          </div>

          <div className="pt-2 flex justify-end gap-3">
            <Link
              href="/work-items"
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              {createMutation.isPending ? "Creating..." : "Create Work Item"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
