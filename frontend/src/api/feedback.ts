import { apiPost, apiGet } from "./client";

export interface FeedbackRequest {
  message_id: string;
  session_id?: string;
  rating: "like" | "dislike";
  reason?: string;
}

export interface FeedbackResponse {
  id: number;
  message_id: string;
  rating: string;
  success: boolean;
}

export interface FeedbackItem {
  message_id: string;
  rating: "like" | "dislike";
  reason?: string | null;
}

export async function submitFeedback(body: FeedbackRequest): Promise<FeedbackResponse> {
  return apiPost<FeedbackResponse>("/feedback", body);
}

export async function getSessionFeedback(sessionId: string): Promise<FeedbackItem[]> {
  return apiGet<FeedbackItem[]>(`/feedback/session/${sessionId}`);
}
