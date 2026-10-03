import {
  User,
  Team,
  TeamMember,
  WorkItem,
  WorkItemListResponse,
  Comment,
  ActivityLog,
  DashboardStats,
  ApiError,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("newtonite_token");
}

export async function fetchApi<T>(
  endpoint: string,
  options: RequestInit & { idempotencyKey?: string } = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (options.idempotencyKey) {
    headers["Idempotency-Key"] = options.idempotencyKey;
  }

  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    throw {
      code: "NETWORK_ERROR",
      message: `Cannot reach the server at ${url}. Is the backend running?`,
    } as ApiError;
  }

  if (!response.ok) {
    if (response.status === 401 && !endpoint.includes("/auth/login") && !endpoint.includes("/auth/register")) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("newtonite_token");
        window.location.href = "/login";
      }
    }

    let errorData: ApiError;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        code: `HTTP_${response.status}`,
        message: response.statusText || "An unexpected error occurred.",
      };
    }
    throw errorData;
  }

  return response.json();
}

// Auth API
export async function registerApi(data: {
  name: string;
  email: string;
  password: string;
}): Promise<{ access_token: string; user: User }> {
  return fetchApi("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function loginApi(email: string, password: string): Promise<{ access_token: string; user: User }> {
  return fetchApi("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMeApi(): Promise<User> {
  return fetchApi("/auth/me");
}

// Teams API
export async function getTeamsApi(): Promise<Team[]> {
  return fetchApi("/teams");
}

export async function createTeamApi(name: string): Promise<Team> {
  return fetchApi("/teams", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function getTeamMembersApi(teamId: number): Promise<TeamMember[]> {
  return fetchApi(`/teams/${teamId}/members`);
}

export async function addTeamMemberApi(
  teamId: number,
  data: { email?: string; user_id?: number; role: "MEMBER" | "MANAGER" }
): Promise<TeamMember> {
  return fetchApi(`/teams/${teamId}/members`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Work Items API
export async function getDashboardStatsApi(): Promise<DashboardStats> {
  return fetchApi("/dashboard/stats");
}

export interface ListWorkItemsParams {
  search?: string;
  status?: string;
  priority?: string;
  team_id?: number;
  assignee_id?: number;
  unassigned_only?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export async function getWorkItemsApi(params: ListWorkItemsParams = {}): Promise<WorkItemListResponse> {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.status) query.set("status", params.status);
  if (params.priority) query.set("priority", params.priority);
  if (params.team_id) query.set("team_id", params.team_id.toString());
  if (params.assignee_id) query.set("assignee_id", params.assignee_id.toString());
  if (params.unassigned_only) query.set("unassigned_only", "true");
  if (params.page) query.set("page", params.page.toString());
  if (params.page_size) query.set("page_size", params.page_size.toString());
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);

  const qs = query.toString();
  return fetchApi(`/work-items${qs ? `?${qs}` : ""}`);
}

export async function getWorkItemApi(id: number): Promise<WorkItem> {
  return fetchApi(`/work-items/${id}`);
}

export async function createWorkItemApi(
  data: {
    title: string;
    description?: string;
    priority: string;
    team_id: number;
    assignee_id?: number;
    due_date?: string;
  },
  idempotencyKey?: string
): Promise<WorkItem> {
  return fetchApi("/work-items", {
    method: "POST",
    body: JSON.stringify(data),
    idempotencyKey,
  });
}

export async function updateWorkItemApi(
  id: number,
  data: {
    version: number;
    title?: string;
    description?: string | null;
    status?: string;
    priority?: string;
    due_date?: string | null;
  }
): Promise<WorkItem> {
  return fetchApi(`/work-items/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function claimWorkItemApi(id: number): Promise<WorkItem> {
  return fetchApi(`/work-items/${id}/claim`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function assignWorkItemApi(
  id: number,
  version: number,
  assignee_id: number | null
): Promise<WorkItem> {
  return fetchApi(`/work-items/${id}/assign`, {
    method: "POST",
    body: JSON.stringify({ version, assignee_id }),
  });
}

// Comments API
export async function getCommentsApi(workItemId: number): Promise<Comment[]> {
  return fetchApi(`/work-items/${workItemId}/comments`);
}

export async function addCommentApi(workItemId: number, content: string): Promise<Comment> {
  return fetchApi(`/work-items/${workItemId}/comments`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

// Activity Logs API
export async function getActivityLogsApi(workItemId: number): Promise<ActivityLog[]> {
  return fetchApi(`/work-items/${workItemId}/activity`);
}
