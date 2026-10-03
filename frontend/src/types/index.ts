export type Role = "MEMBER" | "MANAGER" | "ADMIN";

export type WorkItemStatus = "OPEN" | "IN_PROGRESS" | "BLOCKED" | "RESOLVED" | "CLOSED";

export const ALLOWED_TRANSITIONS: Record<WorkItemStatus, WorkItemStatus[]> = {
  OPEN: ["IN_PROGRESS", "BLOCKED", "CLOSED"],
  IN_PROGRESS: ["OPEN", "BLOCKED", "RESOLVED"],
  BLOCKED: ["OPEN", "IN_PROGRESS"],
  RESOLVED: ["IN_PROGRESS", "CLOSED"],
  CLOSED: ["OPEN"],
};

export type WorkItemPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export interface TeamMembership {
  team_id: number;
  team_name: string;
  role: Role;
}

export interface User {
  id: number;
  name: string;
  email: string;
  is_admin: boolean;
  created_at: string;
  memberships: TeamMembership[];
}

export interface Team {
  id: number;
  name: string;
  created_at: string;
  member_count?: number;
}

export interface TeamMember {
  id: number;
  user_id: number;
  team_id: number;
  user_name: string;
  user_email: string;
  role: Role;
  created_at: string;
}

export interface WorkItem {
  id: number;
  title: string;
  description: string | null;
  status: WorkItemStatus;
  priority: WorkItemPriority;
  team_id: number;
  team_name: string;
  assignee_id: number | null;
  assignee_name: string | null;
  created_by: number;
  creator_name: string;
  due_date: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WorkItemListResponse {
  items: WorkItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Comment {
  id: number;
  work_item_id: number;
  author_id: number;
  author_name: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface ActivityLog {
  id: number;
  work_item_id: number;
  actor_id: number;
  actor_name: string;
  action: string;
  old_value: string | null;
  new_value: string | null;
  created_at: string;
}

export interface DashboardStats {
  open_count: number;
  in_progress_count: number;
  urgent_count: number;
  blocked_count: number;
  my_assigned_count: number;
  my_assigned_items: WorkItem[];
  urgent_items: WorkItem[];
  recent_items: WorkItem[];
}

export interface ApiError {
  code: string;
  message: string;
  detail?: any;
}
