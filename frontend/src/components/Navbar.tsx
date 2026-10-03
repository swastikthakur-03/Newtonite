"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { RoleBadge } from "./Badge";
import { LayoutDashboard, CheckSquare, Users, PlusCircle, LogOut } from "lucide-react";

export function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user || pathname === "/login" || pathname === "/register") return null;

  const navLinks = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/work-items", label: "Work Items", icon: CheckSquare },
    { href: "/teams", label: "Teams", icon: Users },
  ];

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                N
              </div>
              <span className="font-semibold text-gray-900 text-lg tracking-tight">
                Newtonite <span className="text-xs font-normal text-gray-500 uppercase tracking-wider ml-1 bg-gray-100 px-1.5 py-0.5 rounded">Ops</span>
              </span>
            </Link>

            <nav className="hidden md:flex space-x-1">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = pathname === link.href || pathname.startsWith(`${link.href}/`);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`inline-flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <Link
              href="/work-items/new"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              New Work Item
            </Link>

            <div className="h-6 w-px bg-gray-200" />

            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-sm font-medium text-gray-900 leading-tight">{user.name}</div>
                <div className="flex items-center justify-end gap-1.5 mt-0.5">
                  {user.is_admin ? (
                    <RoleBadge role="ADMIN" />
                  ) : user.memberships && user.memberships.length > 0 ? (
                    <RoleBadge role={user.memberships[0].role} />
                  ) : (
                    <span className="text-xs text-gray-400">No Team</span>
                  )}
                  <span className="text-xs text-gray-500">
                    {user.is_admin
                      ? "System Admin"
                      : user.memberships && user.memberships.length > 0
                      ? user.memberships.map((m) => m.team_name).join(", ")
                      : ""}
                  </span>
                </div>
              </div>

              <button
                onClick={logout}
                className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
                title="Log out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
