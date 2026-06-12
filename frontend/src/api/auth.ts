import { apiPost } from "./client";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  id: number;
  name: string;
  email: string;
  role: "staff" | "executive" | "admin";
  department: string;
  avatar: string | null;
}

export function login(data: LoginRequest): Promise<LoginResponse> {
  return apiPost<LoginResponse>("/auth/login", data);
}
