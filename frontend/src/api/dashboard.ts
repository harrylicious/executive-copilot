import { apiGet } from "./client";

// ─── Dashboard Analytics API ─────────────────────────────────────────────────

export interface KPIData {
  total_documents: number;
  total_queries_today: number;
  active_departments: number;
  ai_accuracy: number;
}

export interface DeptDistribution {
  department: string;
  query_count: number;
}

export interface QueryTrend {
  date: string;
  count: number;
}

export interface RecentActivity {
  department: string;
  description: string;
  activity_type: string;
  timestamp: string;
}

export interface DashboardAnalytics {
  kpi: KPIData;
  department_distribution: DeptDistribution[];
  query_trend: QueryTrend[];
  recent_activities: RecentActivity[];
}

export async function getDashboardAnalytics(): Promise<DashboardAnalytics> {
  return apiGet<DashboardAnalytics>("/dashboard/analytics");
}
