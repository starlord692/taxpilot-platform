export interface ApiError { detail?: string; message?: string; code?: string; errors?: Record<string, string[]>; }
export interface ApiResponse<T> { data: T; message?: string; }
export interface PaginatedResponse<T> { items: T[]; page: number; pageSize: number; total: number; }
