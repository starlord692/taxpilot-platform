import { useAuth } from "@/contexts/auth-context";
export function useLogout() { return useAuth().logout; }
