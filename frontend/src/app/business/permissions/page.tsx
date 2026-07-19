"use client";
import { useAuth } from "@/contexts/auth-context";
import { PermissionCard } from "@/components/business/permission-card";
export default function BusinessPermissionsPage() { const { user } = useAuth(); return <PermissionCard roles={user?.roles} permissions={user?.permissions} />; }
