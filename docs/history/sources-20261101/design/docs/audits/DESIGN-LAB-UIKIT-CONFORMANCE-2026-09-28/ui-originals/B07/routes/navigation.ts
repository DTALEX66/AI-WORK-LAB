import { routes } from "./routes";
export const primaryNav = routes.filter((r) => !r.path.includes(":id"));
