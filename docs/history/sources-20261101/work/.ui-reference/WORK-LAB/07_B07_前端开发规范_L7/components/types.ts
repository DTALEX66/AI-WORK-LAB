export type ProjectId = "WORK-LAB";

export type DomainState =
  | "draft"
  | "ready"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "blocked"
  | "approval_required";

export type Role =
  | "Owner"
  | "Admin"
  | "Operator"
  | "Auditor"
  | "Viewer";

export interface PageMeta {
  id: string;
  title: string;
  route: string;
  requiredPermission?: string;
}

export interface AuditMeta {
  actor: string;
  action: string;
  resource: string;
  timestamp: string;
  result: "success" | "warning" | "error";
}
