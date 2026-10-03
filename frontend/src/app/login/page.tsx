"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ShieldCheck, UserCheck, KeyRound, AlertCircle, ArrowRight } from "lucide-react";

interface Persona {
  name: string;
  email: string;
  role: string;
  team: string;
  description: string;
}

const DEMO_PERSONAS: Persona[] = [
  {
    name: "Alex Mercer",
    email: "admin@newtonite.internal",
    role: "ADMIN",
    team: "All Teams",
    description: "System-wide admin authority across all operational teams and resources.",
  },
  {
    name: "Priya Sharma",
    email: "priya.manager@newtonite.internal",
    role: "MANAGER",
    team: "Engineering Core",
    description: "Can assign tasks, change priority, and manage Engineering items.",
  },
  {
    name: "Rahul Verma",
    email: "rahul.member@newtonite.internal",
    role: "MEMBER",
    team: "Engineering Core",
    description: "Can claim unassigned work, update assigned status, and post comments.",
  },
  {
    name: "Swastik Roy",
    email: "swastik.ops@newtonite.internal",
    role: "MANAGER",
    team: "Customer Operations",
    description: "Manages customer operational tasks and compliance workflows.",
  },
  {
    name: "Ananya Patel",
    email: "ananya.fraud@newtonite.internal",
    role: "MEMBER",
    team: "Payments & Fraud",
    description: "Demonstrates cross-team isolation: cannot access Engineering items.",
  },
];

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.message || "Invalid email or password.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (personaEmail: string) => {
    setEmail(personaEmail);
    setPassword("password123");
    setError(null);
    setLoading(true);
    try {
      await login(personaEmail, "password123");
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.message || "Failed to log in.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-6">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 text-white font-bold text-2xl shadow-sm mb-3">
          N
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Newtonite Operations Portal</h1>
        <p className="text-sm text-gray-500 mt-1">
          Operations Under Pressure — Internal Work Management & Incident Response
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
        {/* Left Column: Form */}
        <div className="md:col-span-5 bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-blue-600" />
            Sign In
          </h2>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-red-700 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Email Address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@newtonite.internal"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <span className="text-[11px] text-gray-400 mt-1 block">Default demo password: password123</span>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-medium transition-colors shadow-sm"
            >
              {loading ? "Authenticating..." : "Sign In to Operations"}
            </button>

            <div className="text-center pt-2">
              <span className="text-xs text-gray-500">Don't have an account? </span>
              <a href="/register" className="text-xs font-medium text-blue-600 hover:underline">
                Create an account
              </a>
            </div>
          </form>
        </div>

        {/* Right Column: Demo Personas */}
        <div className="md:col-span-7 bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-blue-600" />
              Quick Demo Personas
            </h2>
            <span className="text-xs text-gray-500">Click persona to sign in instantly</span>
          </div>

          <div className="space-y-3">
            {DEMO_PERSONAS.map((p) => (
              <div
                key={p.email}
                onClick={() => handleQuickLogin(p.email)}
                className="p-3 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50/50 cursor-pointer transition-all group"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 text-sm">{p.name}</span>
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                        {p.role}
                      </span>
                      <span className="text-xs text-gray-500">• {p.team}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{p.description}</p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all shrink-0 ml-3" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
