export const businessKeys = { all: ["business"] as const, list: () => [...businessKeys.all, "list"] as const, gst: (businessId: string) => [...businessKeys.all, businessId, "gst"] as const };
