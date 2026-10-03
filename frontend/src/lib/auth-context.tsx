"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { User, Role } from "@/types";
import { getMeApi, loginApi, registerApi } from "./api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRoleInTeam: (teamId: number, roles: Role[]) => boolean;
  isGlobalAdmin: () => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const savedToken = localStorage.getItem("newtonite_token");
    if (savedToken) {
      setToken(savedToken);
      getMeApi()
        .then((userData) => {
          setUser(userData);
        })
        .catch(() => {
          localStorage.removeItem("newtonite_token");
          setToken(null);
          setUser(null);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await loginApi(email, password);
      localStorage.setItem("newtonite_token", res.access_token);
      setToken(res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (name: string, email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await registerApi({ name, email, password });
      localStorage.setItem("newtonite_token", res.access_token);
      setToken(res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("newtonite_token");
    setToken(null);
    setUser(null);
    window.location.href = "/login";
  };

  const isGlobalAdmin = (): boolean => {
    if (!user) return false;
    return !!user.is_admin;
  };

  const hasRoleInTeam = (teamId: number, roles: Role[]): boolean => {
    if (!user) return false;
    if (isGlobalAdmin()) return true;
    const membership = user.memberships?.find((m) => m.team_id === teamId);
    if (!membership) return false;
    return roles.includes(membership.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        logout,
        hasRoleInTeam,
        isGlobalAdmin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export function useRequireAuth() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  return { user, isLoading };
}
