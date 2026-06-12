import { apiPost } from "./client";

export type TransformFormat = "table" | "bar" | "line" | "pie" | "donut";

export interface TransformRequest {
  content: string;
  format: TransformFormat;
  language?: "id" | "en";
}

export interface TransformResponse {
  transformed: string;
  format: string;
  success: boolean;
}

export async function transformContent(body: TransformRequest): Promise<TransformResponse> {
  return apiPost<TransformResponse>("/transform", body);
}
