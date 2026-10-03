"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useRequireAuth } from "@/lib/auth-context";
import { getDashboardStatsApi } from "@/lib/api";
import { StatusBadge, PriorityBadge, VersionBadge } from "@/components/Badge";
import {
  AlertTriangle,
  Flame,
  Clock,
  CheckCircle,
  UserCheck,
  ArrowRight,
  PlusCircle,
  Inbox,
  Users,
} from "lucide-react";

export default function DashboardPage() {
  const { user, isLoading: authLoading } = useRequireAuth();

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: getDashboardStatsApi,
    enabled: !!user,
    refetchInterval: 15000, // Light auto-polling for operational awareness
  });

  if (authLoading || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        Failed to load operational dashboard. Please refresh.
      </div>
    );
  }

  const hasNoTeams = !user?.is_admin && (!user?.memberships || user?.memberships.length === 0);

  return (
    <div className="space-y-8">
      {/* No team yet notification */}
      {hasNoTeams && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-800 text-sm flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <Users className="w-5 h-5 shrink-0 mt-0.5 text-amber-600" />
            <div>
              <h3 className="font-semibold text-amber-900">No team assigned yet</h3>
              <p className="mt-0.5 text-amber-700">
                You are registered but not assigned to any team. Contact a team manager to add your email to their team roster.
              </p>
            </div>
          </div>
          <Link
            href="/teams"
            className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-medium shrink-0 transition-colors"
          >
            View Teams
          </Link>
        </div>
      )}
      {/* Welcome & Context Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Operations Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            Real-time status overview answering: <span className="font-medium text-gray-700">"What needs my attention next?"</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/work-items"
            className="inline-flex items-center gap-2 px-3.5 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 shadow-sm transition-colors"
          >
            Browse All Items
          </Link>
          <Link
            href="/work-items/new"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            Create Work Item
          </Link>
        </div>
      </div>

      {/* Primary KPI Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {/* Urgent */}
        <div className="bg-white p-4 rounded-xl border border-red-200 shadow-sm">
          <div className="flex items-center justify-between text-red-600 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Urgent Attention</span>
            <Flame className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-gray-900">{stats?.urgent_count ?? 0}</div>
          <span className="text-xs text-red-600 mt-1 block">Active urgent items</span>
        </div>

        {/* Blocked */}
        <div className="bg-white p-4 rounded-xl border border-amber-200 shadow-sm">
          <div className="flex items-center justify-between text-amber-600 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Blocked Work</span>
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-gray-900">{stats?.blocked_count ?? 0}</div>
          <span className="text-xs text-amber-600 mt-1 block">Requires intervention</span>
        </div>

        {/* My Assigned */}
        <div className="bg-white p-4 rounded-xl border border-blue-200 shadow-sm">
          <div className="flex items-center justify-between text-blue-600 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Assigned to Me</span>
            <UserCheck className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-gray-900">{stats?.my_assigned_count ?? 0}</div>
          <span className="text-xs text-blue-600 mt-1 block">Your personal queue</span>
        </div>

        {/* In Progress */}
        <div className="bg-white p-4 rounded-xl border border-indigo-200 shadow-sm">
          <div className="flex items-center justify-between text-indigo-600 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">In Progress</span>
            <Clock className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-gray-900">{stats?.in_progress_count ?? 0}</div>
          <span className="text-xs text-indigo-600 mt-1 block">Under active work</span>
        </div>

        {/* Open */}
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-gray-600 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Open Backlog</span>
            <CheckCircle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-gray-900">{stats?.open_count ?? 0}</div>
          <span className="text-xs text-gray-500 mt-1 block">Awaiting triage/claim</span>
        </div>
      </div>

      {/* Two Focal Columns: My Queue & Urgent Attention */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: My Assigned Work */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-blue-600" />
              <h2 className="font-semibold text-gray-900">My Assigned Tasks</h2>
            </div>
            <Link
              href={`/work-items?assignee_id=${user?.id}`}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
            >
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {!stats?.my_assigned_items || stats.my_assigned_items.length === 0 ? (
            <div className="text-center py-10 bg-gray-50 rounded-lg border border-dashed border-gray-200 text-gray-500 text-sm">
              <Inbox className="w-8 h-8 text-gray-400 mx-auto mb-2" />
              You currently have no assigned open work items.
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {stats.my_assigned_items.map((item) => (
                <Link
                  key={item.id}
                  href={`/work-items/${item.id}`}
                  className="block py-3 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors group"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium text-gray-900 text-sm group-hover:text-blue-600 transition-colors truncate">
                        {item.title}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                        <span>{item.team_name}</span>
                        <span>•</span>
                        <VersionBadge version={item.version} />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <PriorityBadge priority={item.priority} />
                      <StatusBadge status={item.status} />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Right: Urgent Operational Work Across Teams */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Flame className="w-5 h-5 text-red-600" />
              <h2 className="font-semibold text-gray-900">Urgent Attention Needed</h2>
            </div>
            <Link
              href="/work-items?priority=URGENT"
              className="text-xs text-red-600 hover:text-red-800 font-medium flex items-center gap-1"
            >
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {!stats?.urgent_items || stats.urgent_items.length === 0 ? (
            <div className="text-center py-10 bg-gray-50 rounded-lg border border-dashed border-gray-200 text-gray-500 text-sm">
              <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              No active urgent items in your teams!
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {stats.urgent_items.map((item) => (
                <Link
                  key={item.id}
                  href={`/work-items/${item.id}`}
                  className="block py-3 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors group"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium text-gray-900 text-sm group-hover:text-red-600 transition-colors truncate">
                        {item.title}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                        <span>{item.team_name}</span>
                        <span>•</span>
                        <span>Assignee: {item.assignee_name || "Unassigned"}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <StatusBadge status={item.status} />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Section: Recently Updated Operational Flow */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-gray-600" />
            <h2 className="font-semibold text-gray-900">Recently Updated Work Items</h2>
          </div>
          <Link
            href="/work-items"
            className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
          >
            All Work Items <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs text-gray-700 uppercase tracking-wider border-b border-gray-200">
              <tr>
                <th className="px-4 py-3">Work Item</th>
                <th className="px-4 py-3">Team</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Assignee</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Last Modified</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {stats?.recent_items?.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    <Link href={`/work-items/${item.id}`} className="hover:text-blue-600 truncate block max-w-md">
                      {item.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{item.team_name}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3">
                    <PriorityBadge priority={item.priority} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-700">
                    {item.assignee_name ? (
                      <span className="font-medium">{item.assignee_name}</span>
                    ) : (
                      <span className="text-amber-600 font-medium bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                        Unassigned
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <VersionBadge version={item.version} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(item.updated_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
