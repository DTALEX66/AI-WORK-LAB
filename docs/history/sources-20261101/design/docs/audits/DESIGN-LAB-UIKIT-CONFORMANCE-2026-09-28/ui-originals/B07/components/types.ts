export type ProjectId = "DESIGN-LAB";

export type DomainState =
  | "brief"
  | "research"
  | "designing"
  | "review"
  | "qa"
  | "approved"
  | "delivered"
  | "archived";

export type Role =
  | "Owner"
  | "DesignLead"
  | "Designer"
  | "Reviewer"
  | "Producer"
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
