"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRequireAuth, useAuth } from "@/lib/auth-context";
import {
  getWorkItemApi,
  updateWorkItemApi,
  claimWorkItemApi,
  assignWorkItemApi,
  getCommentsApi,
  addCommentApi,
  getActivityLogsApi,
  getTeamMembersApi,
} from "@/lib/api";
import { StatusBadge, PriorityBadge, VersionBadge, RoleBadge } from "@/components/Badge";
import { WorkItemStatus, WorkItemPriority, ApiError, ALLOWED_TRANSITIONS } from "@/types";
import {
  ArrowLeft,
  UserCheck,
  UserPlus,
  RefreshCw,
  AlertTriangle,
  Send,
  MessageSquare,
  History,
  CheckCircle2,
  Calendar,
  Users,
  User,
  ShieldAlert,
} from "lucide-react";

export default function WorkItemDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useRequireAuth();
  const { hasRoleInTeam } = useAuth();

  const workItemId = Number(params.id);

  // Optimistic concurrency conflict state
  const [conflictError, setConflictError] = useState<string | null>(null);
  const [commentText, setCommentText] = useState("");
  const [selectedAssignee, setSelectedAssignee] = useState<string>("");

  // Queries
  const {
    data: item,
    isLoading: itemLoading,
    error: itemError,
    refetch: refetchItem,
  } = useQuery({
    queryKey: ["work-item", workItemId],
    queryFn: () => getWorkItemApi(workItemId),
    enabled: !isNaN(workItemId) && !!user,
  });

  const { data: teamMembers } = useQuery({
    queryKey: ["team-members", item?.team_id],
    queryFn: () => getTeamMembersApi(item!.team_id),
    enabled: !!item?.team_id,
  });

  const { data: comments, refetch: refetchComments } = useQuery({
    queryKey: ["comments", workItemId],
    queryFn: () => getCommentsApi(workItemId),
    enabled: !isNaN(workItemId) && !!user,
  });

  const { data: activityLogs, refetch: refetchActivity } = useQuery({
    queryKey: ["activity", workItemId],
    queryFn: () => getActivityLogsApi(workItemId),
    enabled: !isNaN(workItemId) && !!user,
  });

  const canManage = item ? hasRoleInTeam(item.team_id, ["MANAGER", "ADMIN"]) : false;

  const refreshAll = () => {
    setConflictError(null);
    refetchItem();
    refetchComments();
    refetchActivity();
  };

  // Mutations
  const updateStatusMutation = useMutation({
    mutationFn: (newStatus: WorkItemStatus) =>
      updateWorkItemApi(workItemId, { version: item!.version, status: newStatus }),
    onSuccess: () => {
      setConflictError(null);
      refreshAll();
    },
    onError: (err: ApiError) => {
      refreshAll();
      if (err.code === "VERSION_CONFLICT") {
        setConflictError("This work item was modified by another user. Current server state has been loaded.");
      } else {
        alert(err.message || "Failed to update status.");
      }
    },
  });

  const updatePriorityMutation = useMutation({
    mutationFn: (newPriority: WorkItemPriority) =>
      updateWorkItemApi(workItemId, { version: item!.version, priority: newPriority }),
    onSuccess: () => {
      setConflictError(null);
      refreshAll();
    },
    onError: (err: ApiError) => {
      refreshAll();
      if (err.code === "VERSION_CONFLICT") {
        setConflictError("This work item was modified by another user. Current server state has been loaded.");
      } else {
        alert(err.message || "Failed to update priority.");
      }
    },
  });

  const claimMutation = useMutation({
    mutationFn: () => claimWorkItemApi(workItemId),
    onSuccess: () => {
      setConflictError(null);
      refreshAll();
    },
    onError: (err: ApiError) => {
      refreshAll();
      if (err.code === "ALREADY_ASSIGNED" || err.code === "VERSION_CONFLICT" || err.code === "ITEM_NOT_CLAIMABLE") {
        setConflictError(err.message || "This work item cannot be claimed or was already claimed.");
      } else {
        alert(err.message || "Failed to claim work item.");
      }
    },
  });

  const assignMutation = useMutation({
    mutationFn: (targetAssigneeId: number | null) =>
      assignWorkItemApi(workItemId, item!.version, targetAssigneeId),
    onSuccess: () => {
      setConflictError(null);
      setSelectedAssignee("");
      refreshAll();
    },
    onError: (err: ApiError) => {
      refreshAll();
      if (err.code === "VERSION_CONFLICT") {
        setConflictError("This work item was modified by another user. Current server state has been loaded.");
      } else {
        alert(err.message || "Failed to assign work item.");
      }
    },
  });

  const commentMutation = useMutation({
    mutationFn: (content: string) => addCommentApi(workItemId, content),
    onSuccess: () => {
      setCommentText("");
      refetchComments();
      refetchActivity();
    },
    onError: (err: ApiError) => {
      alert(err.message || "Failed to post comment.");
    },
  });

  const handlePostComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    commentMutation.mutate(commentText.trim());
  };

  if (itemLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (itemError || !item) {
    const errorObj = itemError as unknown as ApiError;
    return (
      <div className="max-w-2xl mx-auto py-12 text-center">
        <ShieldAlert className="w-12 h-12 text-red-500 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-gray-900">Access Denied or Not Found</h2>
        <p className="text-sm text-gray-500 mt-1 mb-4">
          {errorObj?.message || "You do not have permission to view this work item or it does not exist."}
        </p>
        <Link
          href="/work-items"
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Work Items
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Back button */}
      <div>
        <Link
          href="/work-items"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Work Items
        </Link>
      </div>

      {/* Optimistic Concurrency Conflict Banner */}
      {conflictError && (
        <div className="p-4 bg-red-50 border-2 border-red-300 rounded-xl flex items-start justify-between gap-4 shadow-sm animate-pulse">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-semibold text-red-900">Optimistic Concurrency Conflict (409)</h4>
              <p className="text-sm text-red-700 mt-0.5">{conflictError}</p>
            </div>
          </div>
          <button
            onClick={refreshAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh Latest State
          </button>
        </div>
      )}

      {/* Header Card */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-medium text-gray-400">WI-{item.id}</span>
              <span className="text-gray-300">•</span>
              <VersionBadge version={item.version} />
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 leading-snug">{item.title}</h1>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <PriorityBadge priority={item.priority} />
            <StatusBadge status={item.status} />
          </div>
        </div>

        {/* Operational Context Metadata Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-gray-100 text-xs">
          <div>
            <span className="text-gray-400 block mb-0.5">Team</span>
            <span className="font-medium text-gray-900 flex items-center gap-1">
              <Users className="w-3.5 h-3.5 text-gray-400" />
              {item.team_name}
            </span>
          </div>

          <div>
            <span className="text-gray-400 block mb-0.5">Current Owner</span>
            {item.assignee_name ? (
              <span className="font-medium text-gray-900 flex items-center gap-1">
                <User className="w-3.5 h-3.5 text-blue-500" />
                {item.assignee_name}
              </span>
            ) : (
              <span className="text-amber-700 font-semibold bg-amber-50 px-2 py-0.5 rounded border border-amber-200 inline-block">
                Unassigned
              </span>
            )}
          </div>

          <div>
            <span className="text-gray-400 block mb-0.5">Created By</span>
            <span className="font-medium text-gray-900">{item.creator_name}</span>
          </div>

          <div>
            <span className="text-gray-400 block mb-0.5">Due Date</span>
            <span className="font-medium text-gray-900 flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-gray-400" />
              {item.due_date ? new Date(item.due_date).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) : "None"}
            </span>
          </div>
        </div>

        {/* Description */}
        {item.description && (
          <div className="pt-3 border-t border-gray-100">
            <span className="text-xs font-semibold uppercase text-gray-400 tracking-wider block mb-1">Description</span>
            <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">{item.description}</p>
          </div>
        )}
      </div>

      {/* Action Controls Toolbar */}
      <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-700">Operational Actions</h2>

        <div className="flex flex-wrap items-center gap-4">
          {/* 1. Claim Action (if unassigned) */}
          {item.assignee_id === null && (
            <button
              onClick={() => claimMutation.mutate()}
              disabled={claimMutation.isPending}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium shadow-sm transition-colors"
            >
              <UserCheck className="w-4 h-4" />
              {claimMutation.isPending ? "Claiming..." : "Claim This Work Item"}
            </button>
          )}

          {/* 2. Status Selector (Current status + legal next transitions) */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Status:</span>
            <select
              value={item.status}
              onChange={(e) => updateStatusMutation.mutate(e.target.value as WorkItemStatus)}
              disabled={updateStatusMutation.isPending}
              className="text-xs font-medium px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={item.status}>{item.status} (Current)</option>
              {(ALLOWED_TRANSITIONS[item.status] || []).map((nextStatus) => (
                <option key={nextStatus} value={nextStatus}>
                  {nextStatus}
                </option>
              ))}
            </select>
          </div>

          {/* 3. Priority Selector (Manager / Admin) */}
          {canManage && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 font-medium">Priority:</span>
              <select
                value={item.priority}
                onChange={(e) => updatePriorityMutation.mutate(e.target.value as WorkItemPriority)}
                disabled={updatePriorityMutation.isPending}
                className="text-xs font-medium px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="URGENT">URGENT</option>
              </select>
            </div>
          )}

          {/* 4. Assign / Reassign (Manager / Admin) */}
          {canManage && teamMembers && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 font-medium">Reassign:</span>
              <select
                value={selectedAssignee}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedAssignee(val);
                  if (val !== "") {
                    assignMutation.mutate(val === "unassign" ? null : Number(val));
                  }
                }}
                disabled={assignMutation.isPending}
                className="text-xs font-medium px-2.5 py-1.5 border border-gray-300 rounded-lg bg-white hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select Teammate...</option>
                <option value="unassign">-- Unassign Item --</option>
                {teamMembers.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.user_name} ({m.role})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Two Column Layout: Comments & Activity Log */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Comments (7 cols) */}
        <div className="lg:col-span-7 bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-3">
            <MessageSquare className="w-4 h-4 text-blue-600" />
            <h3 className="font-semibold text-gray-900 text-sm">Comments & Notes ({comments?.length ?? 0})</h3>
          </div>

          {/* Comment list */}
          <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
            {!comments || comments.length === 0 ? (
              <p className="text-xs text-gray-400 italic py-4 text-center">No comments posted yet.</p>
            ) : (
              comments.map((c) => (
                <div key={c.id} className="p-3 bg-gray-50 rounded-lg border border-gray-100 space-y-1 text-xs">
                  <div className="flex items-center justify-between text-gray-500">
                    <span className="font-semibold text-gray-900">{c.author_name}</span>
                    <span>
                      {new Date(c.created_at).toLocaleDateString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="text-gray-700 whitespace-pre-wrap">{c.content}</p>
                </div>
              ))
            )}
          </div>

          {/* Add comment input */}
          <form onSubmit={handlePostComment} className="pt-3 border-t border-gray-100 flex gap-2">
            <input
              type="text"
              placeholder="Add an update or investigation note..."
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={commentMutation.isPending || !commentText.trim()}
              className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition-colors flex items-center gap-1 shrink-0"
            >
              <Send className="w-3.5 h-3.5" />
              Post
            </button>
          </form>
        </div>

        {/* Right Column: Transactional Activity Audit Trail (5 cols) */}
        <div className="lg:col-span-5 bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-3">
            <History className="w-4 h-4 text-blue-600" />
            <h3 className="font-semibold text-gray-900 text-sm">Activity History</h3>
          </div>

          <div className="space-y-4 max-h-96 overflow-y-auto pr-1">
            {!activityLogs || activityLogs.length === 0 ? (
              <p className="text-xs text-gray-400 italic py-4 text-center">No activity records found.</p>
            ) : (
              activityLogs.map((log) => (
                <div key={log.id} className="relative pl-5 border-l-2 border-blue-200 text-xs space-y-0.5">
                  <div className="w-2 h-2 rounded-full bg-blue-600 absolute -left-[5px] top-1" />
                  <div className="flex items-center justify-between text-gray-500 text-[11px]">
                    <span className="font-semibold text-gray-900">{log.actor_name}</span>
                    <span>
                      {new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                  <div className="text-gray-700 font-medium">
                    {log.action === "CREATED" && "Created this work item"}
                    {log.action === "STATUS_CHANGED" && `Status changed: ${log.old_value} → ${log.new_value}`}
                    {log.action === "PRIORITY_CHANGED" && `Priority changed: ${log.old_value} → ${log.new_value}`}
                    {log.action === "CLAIMED" && `Claimed this work item`}
                    {log.action === "ASSIGNED" && `Assigned to: ${log.new_value}`}
                    {log.action === "UNASSIGNED" && `Unassigned this item`}
                    {log.action === "COMMENTED" && `Commented: "${log.new_value}"`}
                    {log.action === "DETAILS_UPDATED" && `Updated work item details`}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
