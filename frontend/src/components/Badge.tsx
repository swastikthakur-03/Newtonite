import React from "react";
import { WorkItemStatus, WorkItemPriority, Role } from "@/types";

export function StatusBadge({ status }: { status: WorkItemStatus | string }) {
  const configs: Record<string, { bg: string; dot: string; label: string }> = {
    OPEN: { bg: "bg-blue-50 text-blue-700 border-blue-200", dot: "bg-blue-500", label: "Open" },
    IN_PROGRESS: { bg: "bg-indigo-50 text-indigo-700 border-indigo-200", dot: "bg-indigo-500", label: "In Progress" },
    BLOCKED: { bg: "bg-amber-50 text-amber-800 border-amber-200", dot: "bg-amber-500", label: "Blocked" },
    RESOLVED: { bg: "bg-emerald-50 text-emerald-700 border-emerald-200", dot: "bg-emerald-500", label: "Resolved" },
    CLOSED: { bg: "bg-gray-100 text-gray-700 border-gray-200", dot: "bg-gray-400", label: "Closed" },
  };

  const conf = configs[status] || { bg: "bg-gray-50 text-gray-700 border-gray-200", dot: "bg-gray-400", label: status };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${conf.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${conf.dot}`} />
      {conf.label}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: WorkItemPriority | string }) {
  const configs: Record<string, { bg: string; label: string }> = {
    URGENT: { bg: "bg-red-100 text-red-800 border-red-300 font-semibold", label: "Urgent" },
    HIGH: { bg: "bg-orange-100 text-orange-800 border-orange-200", label: "High" },
    MEDIUM: { bg: "bg-amber-50 text-amber-800 border-amber-200", label: "Medium" },
    LOW: { bg: "bg-slate-100 text-slate-700 border-slate-200", label: "Low" },
  };

  const conf = configs[priority] || { bg: "bg-gray-100 text-gray-700 border-gray-200", label: priority };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${conf.bg}`}>
      {conf.label}
    </span>
  );
}

export function RoleBadge({ role }: { role: Role | string }) {
  const configs: Record<string, { bg: string }> = {
    ADMIN: { bg: "bg-purple-100 text-purple-800 border-purple-200" },
    MANAGER: { bg: "bg-blue-100 text-blue-800 border-blue-200" },
    MEMBER: { bg: "bg-gray-100 text-gray-700 border-gray-200" },
  };

  const conf = configs[role] || { bg: "bg-gray-100 text-gray-700 border-gray-200" };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${conf.bg}`}>
      {role}
    </span>
  );
}

export function VersionBadge({ version }: { version: number }) {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono bg-gray-100 text-gray-600 border border-gray-200" title="Entity Version (Optimistic Concurrency Control)">
      v{version}
    </span>
  );
}
