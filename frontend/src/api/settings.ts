// ─── Settings API ────────────────────────────────────────────────────────────

const API_BASE = "/api";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ProfileSettings {
  name?: string;
  email?: string;
  phone?: string;
  bio?: string;
  avatar?: string;
}

export interface NotificationSettings {
  emailNotifications: boolean;
  pushNotifications: boolean;
  weeklyDigest: boolean;
}

export interface ChatbotSettings {
  language: "id" | "en";
  nuance: string;
  restrictCrossDept: boolean;
}

export interface SecuritySettings {
  twoFactorEnabled: boolean;
  sessionTimeout: number;
}

export interface SettingsResponse {
  profile?: ProfileSettings;
  notifications?: NotificationSettings;
  chatbot?: ChatbotSettings;
  security?: SecuritySettings;
}

export interface SettingsUpdate {
  profile?: ProfileSettings;
  notifications?: NotificationSettings;
  chatbot?: ChatbotSettings;
  security?: SecuritySettings;
}

// ─── API Functions ───────────────────────────────────────────────────────────

export async function getSettings(userId: number): Promise<SettingsResponse> {
  const res = await fetch(`${API_BASE}/settings/${userId}`);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `GET /settings/${userId} failed (${res.status})`);
  }
  return res.json();
}

export async function saveSettings(userId: number, data: SettingsUpdate): Promise<SettingsResponse> {
  const res = await fetch(`${API_BASE}/settings/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `PUT /settings/${userId} failed (${res.status})`);
  }
  return res.json();
}
