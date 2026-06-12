import { apiGet } from "./client";

export interface TreeNode {
  id: string;
  name: string;
  type: string;
  children?: TreeNode[] | null;
  fileId?: number | null;
  color?: string | null;
  description?: string | null;
  outputs?: string[] | null;
  sensitivity?: string | null;
}

export async function fetchDepartments(): Promise<TreeNode[]> {
  return apiGet<TreeNode[]>("/departments");
}
