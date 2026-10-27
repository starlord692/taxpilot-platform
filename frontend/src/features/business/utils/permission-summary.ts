export function permissionModules(permissions: string[] = []) { return [...new Set(permissions.map((permission) => permission.split(".")[0]).filter(Boolean))].sort(); }
