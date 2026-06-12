// ─── User Management API ─────────────────────────────────────────────────────

const API_BASE = "/api";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ─── Types ───────────────────────────────────────────────────────────────────

export interface UserFilters {
  role?: string;
  department?: string;
  status?: string;
  search?: string;
}

export interface UserCreate {
  name: string;
  email: string;
  role: string;
  department: string;
  password: string;
}

export interface UserUpdate {
  name?: string;
  email?: string;
  role?: string;
  department?: string;
  password?: string;
  status?: string;
  phone?: string;
  bio?: string;
  avatar?: string;
}

export interface UserResponse {
  id: number;
  name: string;
  email: string;
  role: string;
  department: string;
  status: string;
  phone?: string;
  bio?: string;
  avatar?: string;
  lastLoginAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface UserListResponse {
  items: UserResponse[];
  total: number;
}

// ─── API Functions ───────────────────────────────────────────────────────────

export async function getUsers(filters?: UserFilters): Promise<UserListResponse> {
  let url = `${API_BASE}/users`;
  if (filters) {
    const params: Record<string, string> = {};
    if (filters.role) params.role = filters.role;
    if (filters.department) params.department = filters.department;
    if (filters.status) params.status = filters.status;
    if (filters.search) params.search = filters.search;
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `GET /users failed (${res.status})`);
  }
  return res.json();
}

export async function createUser(data: UserCreate): Promise<UserResponse> {
  const res = await fetch(`${API_BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `POST /users failed (${res.status})`);
  }
  return res.json();
}

export async function updateUser(id: number, data: UserUpdate): Promise<UserResponse> {
  const res = await fetch(`${API_BASE}/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `PATCH /users/${id} failed (${res.status})`);
  }
  return res.json();
}

export async function deleteUser(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/users/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `DELETE /users/${id} failed (${res.status})`);
  }
}
