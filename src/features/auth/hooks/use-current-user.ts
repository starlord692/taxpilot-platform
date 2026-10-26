import { useQuery } from "@tanstack/react-query";
import { authApi } from "../api/auth-api";
import { authQueryKeys } from "../api/auth-query-keys";
import { getSession } from "@/lib/auth/session-storage";
export function useCurrentUser() { return useQuery({ queryKey: authQueryKeys.me(), queryFn: authApi.me, enabled: Boolean(getSession()), retry: false, staleTime: 60_000 }); }
