export const routes = [
  { path: "/", id: "dashboard", label: "仪表盘" },
  { path: "/projects", id: "projects", label: "项目" },
  { path: "/projects/:id", id: "project-detail", label: "项目详情" },
  { path: "/research", id: "research", label: "研究洞察" },
  { path: "/brand-systems", id: "brand-systems", label: "品牌系统" },
  { path: "/domains", id: "design-domains", label: "设计领域" },
  { path: "/tools", id: "creative-tools", label: "创作工具" },
  { path: "/preflight", id: "preflight-qa", label: "预检 / QA" },
  { path: "/deliverables", id: "deliverables", label: "交付中心" },
  { path: "/evidence", id: "evidence", label: "证据系统" },
  { path: "/collaboration", id: "collaboration", label: "团队协作" },
  { path: "/settings", id: "settings", label: "系统设置" }
] as const;
