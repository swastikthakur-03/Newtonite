"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRequireAuth } from "@/lib/auth-context";
import { getTeamsApi, getTeamMembersApi, addTeamMemberApi, createTeamApi } from "@/lib/api";
import { RoleBadge } from "@/components/Badge";
import { Team, TeamMember } from "@/types";
import { Users, UserPlus, PlusCircle, AlertCircle, Shield, CheckCircle } from "lucide-react";

export default function TeamsPage() {
  const { user, isLoading: authLoading } = useRequireAuth();
  const queryClient = useQueryClient();

  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [newMemberEmail, setNewMemberEmail] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<"MEMBER" | "MANAGER">("MEMBER");
  const [addMemberError, setAddMemberError] = useState<string | null>(null);
  const [addMemberSuccess, setAddMemberSuccess] = useState<string | null>(null);

  // New team creation (system admin only)
  const [newTeamName, setNewTeamName] = useState("");
  const [teamCreateError, setTeamCreateError] = useState<string | null>(null);
  const [teamCreateSuccess, setTeamCreateSuccess] = useState<string | null>(null);

  const { data: teams, isLoading: teamsLoading, error: teamsError } = useQuery<Team[]>({
    queryKey: ["teams"],
    queryFn: getTeamsApi,
    enabled: !!user,
  });

  // Default select first team when loaded
  React.useEffect(() => {
    if (teams && teams.length > 0 && selectedTeamId === null) {
      setSelectedTeamId(teams[0].id);
    }
  }, [teams, selectedTeamId]);

  const { data: members, isLoading: membersLoading } = useQuery<TeamMember[]>({
    queryKey: ["team-members", selectedTeamId],
    queryFn: () => (selectedTeamId ? getTeamMembersApi(selectedTeamId) : Promise.resolve([])),
    enabled: !!selectedTeamId,
  });

  const addMemberMutation = useMutation({
    mutationFn: (data: { teamId: number; email: string; role: "MEMBER" | "MANAGER" }) =>
      addTeamMemberApi(data.teamId, { email: data.email, role: data.role }),
    onSuccess: () => {
      setAddMemberSuccess("Member added successfully!");
      setNewMemberEmail("");
      setAddMemberError(null);
      queryClient.invalidateQueries({ queryKey: ["team-members", selectedTeamId] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
    onError: (err: any) => {
      setAddMemberError(err?.message || "Failed to add member to team.");
      setAddMemberSuccess(null);
      queryClient.invalidateQueries({ queryKey: ["team-members", selectedTeamId] });
    },
  });

  const createTeamMutation = useMutation({
    mutationFn: (name: string) => createTeamApi(name),
    onSuccess: (newTeam) => {
      setTeamCreateSuccess(`Team "${newTeam.name}" created successfully!`);
      setNewTeamName("");
      setTeamCreateError(null);
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      setSelectedTeamId(newTeam.id);
    },
    onError: (err: any) => {
      setTeamCreateError(err?.message || "Failed to create team.");
      setTeamCreateSuccess(null);
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
  });

  if (authLoading || !user) {
    return <div className="text-center py-12 text-sm text-gray-500">Loading operations...</div>;
  }

  // Check if current user is manager of selected team or global admin
  const isManagerOfSelectedTeam =
    user.is_admin ||
    user.memberships?.some(
      (m) => m.team_id === selectedTeamId && (m.role === "MANAGER" || m.role === "ADMIN")
    );

  const handleAddMember = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTeamId || !newMemberEmail.trim()) return;
    setAddMemberError(null);
    setAddMemberSuccess(null);
    addMemberMutation.mutate({
      teamId: selectedTeamId,
      email: newMemberEmail.trim(),
      role: newMemberRole,
    });
  };

  const handleCreateTeam = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamName.trim()) return;
    setTeamCreateError(null);
    setTeamCreateSuccess(null);
    createTeamMutation.mutate(newTeamName.trim());
  };

  const selectedTeam = teams?.find((t) => t.id === selectedTeamId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Teams & Organization</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage operational teams, membership rosters, and access privileges.
        </p>
      </div>

      {/* No team state */}
      {!user.is_admin && (!user.memberships || user.memberships.length === 0) && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-800 text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold">No Team Assigned</h3>
            <p className="mt-1">
              Your account does not currently belong to any team. Contact an existing team manager or administrator to be added to a team roster.
            </p>
          </div>
        </div>
      )}

      {/* Admin Team Creation Panel */}
      {user.is_admin && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2 mb-3">
            <PlusCircle className="w-4 h-4 text-blue-600" />
            Create New Operational Team (System Admin)
          </h2>

          {teamCreateError && (
            <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{teamCreateError}</span>
            </div>
          )}

          {teamCreateSuccess && (
            <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>{teamCreateSuccess}</span>
            </div>
          )}

          <form onSubmit={handleCreateTeam} className="flex gap-3 max-w-xl">
            <input
              type="text"
              required
              value={newTeamName}
              onChange={(e) => setNewTeamName(e.target.value)}
              placeholder="Team name (e.g. Compliance & Risk)"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={createTeamMutation.isPending}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {createTeamMutation.isPending ? "Creating..." : "Create Team"}
            </button>
          </form>
        </div>
      )}

      {/* Teams Grid Layout */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
        {/* Left Column: Teams List */}
        <div className="md:col-span-4 bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Users className="w-4 h-4 text-gray-500" />
            Teams ({teams?.length || 0})
          </h2>

          {teamsLoading ? (
            <div className="text-xs text-gray-400 py-4 text-center">Loading teams...</div>
          ) : teamsError ? (
            <div className="text-xs text-red-500 py-4 text-center">Failed to load teams.</div>
          ) : !teams || teams.length === 0 ? (
            <div className="text-xs text-gray-400 py-4 text-center">No teams found.</div>
          ) : (
            <div className="space-y-2">
              {teams.map((t) => {
                const isSelected = t.id === selectedTeamId;
                return (
                  <button
                    key={t.id}
                    onClick={() => {
                      setSelectedTeamId(t.id);
                      setAddMemberError(null);
                      setAddMemberSuccess(null);
                    }}
                    className={`w-full text-left p-3 rounded-lg border transition-all ${
                      isSelected
                        ? "border-blue-500 bg-blue-50/50 text-blue-900"
                        : "border-gray-200 hover:border-gray-300 hover:bg-gray-50 text-gray-700"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{t.name}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">
                        {t.member_count ?? 0} members
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Team Roster & Add Member Form */}
        <div className="md:col-span-8 space-y-6">
          {selectedTeam ? (
            <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between border-b border-gray-200 pb-4 mb-5">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{selectedTeam.name}</h2>
                  <span className="text-xs text-gray-500">
                    Team ID: #{selectedTeam.id} • Created: {new Date(selectedTeam.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Members List */}
              <div className="mb-6">
                <h3 className="text-xs font-semibold uppercase text-gray-500 tracking-wider mb-3">
                  Team Members ({members?.length || 0})
                </h3>

                {membersLoading ? (
                  <div className="text-xs text-gray-400 py-4 text-center">Loading members...</div>
                ) : !members || members.length === 0 ? (
                  <div className="text-xs text-gray-400 py-4 text-center border border-dashed rounded-lg">
                    No members in this team yet.
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
                    {members.map((m) => (
                      <div key={m.id} className="p-3.5 flex items-center justify-between bg-white hover:bg-gray-50">
                        <div>
                          <div className="text-sm font-medium text-gray-900">{m.user_name}</div>
                          <div className="text-xs text-gray-500">{m.user_email}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <RoleBadge role={m.role} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Add Member Form (Managers and Admins only) */}
              {isManagerOfSelectedTeam ? (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-3">
                    <UserPlus className="w-4 h-4 text-blue-600" />
                    Add Member to {selectedTeam.name}
                  </h3>

                  {addMemberError && (
                    <div className="mb-3 p-2.5 bg-red-50 border border-red-200 rounded-md text-red-700 text-xs flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>{addMemberError}</span>
                    </div>
                  )}

                  {addMemberSuccess && (
                    <div className="mb-3 p-2.5 bg-green-50 border border-green-200 rounded-md text-green-700 text-xs flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 shrink-0" />
                      <span>{addMemberSuccess}</span>
                    </div>
                  )}

                  <form onSubmit={handleAddMember} className="space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="sm:col-span-2">
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          User Email Address
                        </label>
                        <input
                          type="email"
                          required
                          value={newMemberEmail}
                          onChange={(e) => setNewMemberEmail(e.target.value)}
                          placeholder="user@newtonite.internal"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Team Role
                        </label>
                        <select
                          value={newMemberRole}
                          onChange={(e) => setNewMemberRole(e.target.value as "MEMBER" | "MANAGER")}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="MEMBER">MEMBER</option>
                          <option value="MANAGER">MANAGER</option>
                        </select>
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <button
                        type="submit"
                        disabled={addMemberMutation.isPending}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-md text-sm font-medium transition-colors shadow-sm"
                      >
                        {addMemberMutation.isPending ? "Adding..." : "Add to Team"}
                      </button>
                    </div>
                  </form>
                </div>
              ) : (
                <div className="text-xs text-gray-400 bg-gray-50 p-3 rounded-lg border border-gray-200">
                  Only team managers and system administrators can add members to this team.
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400 text-sm">
              Select a team to view members and permissions.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
