"use client";

import type { FeatureCollection } from "geojson";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth/store";
import { api, buildQuery } from "./client";
import type {
  Alert,
  AlertDetail,
  AlertEvent,
  AlertFilters,
  AlertStatus,
  AuditEntry,
  Job,
  JobCreate,
  NotificationItem,
  Overview,
  Page,
  Preferences,
  PrivacyInfo,
  Region,
  RegionCreate,
  Report,
  ReportFormat,
  Result,
  Role,
  Scene,
  Source,
  Territory,
  TerritoryGeometry,
  User,
} from "./types";

export const keys = {
  overview: ["overview"] as const,
  territories: ["territories"] as const,
  territoryGeometries: ["territory-geometries"] as const,
  regions: (territory?: string) => ["regions", territory ?? "all"] as const,
  region: (id: string) => ["region", id] as const,
  jobs: (regionId?: string, page = 1) => ["jobs", regionId ?? "all", page] as const,
  job: (id: string) => ["job", id] as const,
  result: (id: string) => ["result", id] as const,
  alerts: (f: AlertFilters, page: number, order: string) => ["alerts", f, page, order] as const,
  alertsGeo: (f: AlertFilters) => ["alerts-geo", f] as const,
  alert: (id: string) => ["alert", id] as const,
  reports: ["reports"] as const,
  prefs: ["prefs"] as const,
  notifications: (page: number) => ["notifications", page] as const,
  users: ["users"] as const,
  privacy: ["privacy"] as const,
  sources: ["sources"] as const,
  audit: (page: number) => ["audit", page] as const,
};

const authed = () => useAuth.getState().status === "authenticated";

function alertParams(f: AlertFilters) {
  return {
    status: f.status,
    severity: f.severity,
    territory: f.territory,
    region_id: f.region_id,
    date_from: f.date_from,
    date_to: f.date_to,
    bbox: f.bbox?.join(","),
  };
}

export function useOverview() {
  return useQuery({ queryKey: keys.overview, queryFn: () => api<Overview>("/stats/overview"), enabled: authed(), refetchInterval: 30_000 });
}

export function useTerritories() {
  return useQuery({ queryKey: keys.territories, queryFn: () => api<Territory[]>("/territories"), enabled: authed(), staleTime: 60_000 });
}

/** Público, sin auth: límites para el mapa y el globo (si falla usa la copia estática). */
export function useTerritoryGeometries() {
  return useQuery({
    queryKey: keys.territoryGeometries,
    staleTime: Infinity,
    queryFn: async (): Promise<TerritoryGeometry[]> => {
      try {
        return await api<TerritoryGeometry[]>("/territories/geometries", { auth: false });
      } catch {
        const fc = (await (await fetch("/data/territories.geojson")).json()) as {
          features: { properties: { slug: string }; geometry: TerritoryGeometry["geometry"] }[];
        };
        return fc.features.map((f) => ({ slug: f.properties.slug, geometry: f.geometry }));
      }
    },
  });
}

export function useRegions(territory?: string) {
  return useQuery({ queryKey: keys.regions(territory), queryFn: () => api<Region[]>(`/regions${buildQuery({ territory })}`), enabled: authed() });
}

export function useRegion(id: string) {
  return useQuery({ queryKey: keys.region(id), queryFn: () => api<Region>(`/regions/${id}`), enabled: authed() && !!id });
}

export function useAvailableScenes(regionId: string, start: string, end: string, enabled: boolean) {
  return useQuery({
    queryKey: ["scenes", regionId, start, end],
    queryFn: () => api<Scene[]>(`/regions/${regionId}/scenes${buildQuery({ start, end })}`),
    enabled: authed() && enabled && !!start && !!end,
    staleTime: 10 * 60_000,
    retry: false,
  });
}

export function useJobs(regionId?: string, page = 1) {
  return useQuery({
    queryKey: keys.jobs(regionId, page),
    queryFn: () => api<Page<Job>>(`/jobs${buildQuery({ region_id: regionId, page })}`),
    enabled: authed(),
    placeholderData: keepPreviousData,
    // Solo hacemos polling mientras haya algo corriendo.
    refetchInterval: (q) => (q.state.data?.items.some((j) => j.status === "queued" || j.status === "running") ? 3000 : false),
  });
}

export function useResult(id: string | null) {
  return useQuery({ queryKey: keys.result(id ?? ""), queryFn: () => api<Result>(`/results/${id}`), enabled: authed() && !!id });
}

export function useResultPolygons(id: string | null) {
  return useQuery({
    queryKey: ["result-polygons", id],
    queryFn: () => api<FeatureCollection>(`/results/${id}/polygons`),
    enabled: authed() && !!id,
  });
}

export function useAlerts(filters: AlertFilters, page = 1, order: "recent" | "severity" | "area" = "recent", pageSize = 20) {
  return useQuery({
    queryKey: keys.alerts(filters, page, order),
    queryFn: () => api<Page<Alert>>(`/alerts${buildQuery({ ...alertParams(filters), page, page_size: pageSize, order })}`),
    enabled: authed(),
    placeholderData: keepPreviousData,
  });
}

export function useAlertsGeo(filters: AlertFilters) {
  return useQuery({ queryKey: keys.alertsGeo(filters), queryFn: () => api<FeatureCollection>(`/alerts/geojson${buildQuery(alertParams(filters))}`), enabled: authed() });
}

export function useAlert(id: string) {
  return useQuery({ queryKey: keys.alert(id), queryFn: () => api<AlertDetail>(`/alerts/${id}`), enabled: authed() && !!id });
}

function useInvalidate() {
  const qc = useQueryClient();
  return (...prefixes: string[]) => prefixes.forEach((p) => qc.invalidateQueries({ queryKey: [p] }));
}

export function useUpdateAlertStatus(id: string) {
  const qc = useQueryClient();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { status: AlertStatus; comment?: string }) => api<AlertDetail>(`/alerts/${id}/status`, { method: "PATCH", body }),
    onSuccess: (data) => {
      qc.setQueryData(keys.alert(id), data);
      invalidate("alerts", "alerts-geo", "overview");
    },
  });
}

export function useAddComment(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (comment: string) => api<AlertEvent>(`/alerts/${id}/comments`, { method: "POST", body: { comment } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.alert(id) }),
  });
}

export function useCreateRegion() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (body: RegionCreate) => api<Region>("/regions", { method: "POST", body }), onSuccess: () => invalidate("regions", "overview", "territories") });
}

export function useUpdateRegion(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: Partial<Pick<Region, "name" | "description" | "cadence_days" | "is_active">>) => api<Region>(`/regions/${id}`, { method: "PATCH", body }),
    onSuccess: () => invalidate("regions", "region", "overview"),
  });
}

export function useDeleteRegion() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => api(`/regions/${id}`, { method: "DELETE" }), onSuccess: () => invalidate("regions", "overview", "territories") });
}

export function useSubmitJob(regionId: string) {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (body: JobCreate) => api<Job>(`/regions/${regionId}/jobs`, { method: "POST", body }), onSuccess: () => invalidate("jobs", "regions", "region") });
}

export function useReports() {
  return useQuery({ queryKey: keys.reports, queryFn: () => api<Report[]>("/reports"), enabled: authed() });
}

export function useCreateReport() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { format: ReportFormat; title: string; filters: AlertFilters }) => api<Report>("/reports", { method: "POST", body }),
    onSuccess: () => invalidate("reports"),
  });
}

export function useEmailReport() {
  return useMutation({ mutationFn: ({ id, to }: { id: string; to: string[] }) => api<NotificationItem[]>(`/reports/${id}/email`, { method: "POST", body: { to } }) });
}

export function usePreferences() {
  return useQuery({ queryKey: keys.prefs, queryFn: () => api<Preferences>("/me/preferences"), enabled: authed() });
}

export function useSavePreferences() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (body: Preferences) => api<Preferences>("/me/preferences", { method: "PUT", body }), onSuccess: (d) => qc.setQueryData(keys.prefs, d) });
}

export function useNotifications(page = 1) {
  return useQuery({ queryKey: keys.notifications(page), queryFn: () => api<Page<NotificationItem>>(`/me/notifications?page=${page}`), enabled: authed() });
}

export function useUsers() {
  return useQuery({ queryKey: keys.users, queryFn: () => api<User[]>("/users"), enabled: authed() });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: Role; is_active?: boolean }) => api<User>(`/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.users }),
  });
}

export function usePrivacyInfo() {
  return useQuery({ queryKey: keys.privacy, queryFn: () => api<PrivacyInfo>("/privacy/info", { auth: false }), staleTime: Infinity, retry: false });
}

export function useSources() {
  return useQuery({ queryKey: keys.sources, queryFn: () => api<Source[]>("/sources", { auth: false }), staleTime: Infinity });
}

export function useAudit(page = 1) {
  return useQuery({ queryKey: keys.audit(page), queryFn: () => api<Page<AuditEntry>>(`/audit?page=${page}`), enabled: authed() });
}
