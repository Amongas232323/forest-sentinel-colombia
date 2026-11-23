/**
 * Copia 1:1 de backend/app/schemas/*.py. La fuente de verdad es el backend:
 * hay que regenerar/comparar contra /api/v1/openapi.json cuando cambie el contrato
 * (ver CONTRIBUTING.md › "Contrato API").
 */

import type { MultiPolygon, Polygon } from "geojson";

export type UUID = string;
export type ISODate = string; // YYYY-MM-DD
export type ISODateTime = string;

export type Role = "admin" | "analyst" | "observer";
export type Severity = "low" | "moderate" | "high" | "priority";
export type ChangeSignal = "vegetation_loss" | "possible_burn" | "possible_flooding";
export type AlertStatus = "new" | "pending_review" | "in_review" | "confirmed" | "dismissed" | "closed";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type NotificationFrequency = "immediate" | "daily" | "weekly";
export type ReportFormat = "csv" | "pdf";

export interface ApiErrorBody {
  error: { code: string; message: string; details?: { field: string; message: string }[] };
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface User {
  id: UUID;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: ISODateTime;
  last_login_at: ISODateTime | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export type LonLat = [number, number];
export type BBox = [number, number, number, number];

export type GeoJSONGeometry = Polygon | MultiPolygon;

export interface Territory {
  id: UUID;
  slug: string;
  name: string;
  kind: string;
  description: string;
  area_km2: number;
  attribution: string;
  license: string;
  centroid: LonLat;
  bbox: BBox;
  region_count: number;
  open_alerts: number;
}

export interface TerritoryGeometry {
  slug: string;
  geometry: GeoJSONGeometry;
}

export interface Region {
  id: UUID;
  territory_id: UUID;
  territory_slug: string;
  territory_name: string;
  name: string;
  description: string;
  area_km2: number;
  is_active: boolean;
  cadence_days: number;
  last_run_at: ISODateTime | null;
  created_at: ISODateTime;
  centroid: LonLat;
  bbox: BBox;
  geometry: GeoJSONGeometry;
  open_alerts: number;
  last_job_status: JobStatus | null;
}

export interface RegionCreate {
  territory_slug: string;
  name: string;
  description?: string;
  geometry: GeoJSONGeometry;
  cadence_days?: number;
}

export interface Scene {
  scene_id: string;
  collection: string;
  acquired_at: ISODateTime;
  cloud_cover: number | null;
  tile_id: string | null;
}

export interface JobCreate {
  reference_start: ISODate;
  reference_end: ISODate;
  observation_start: ISODate;
  observation_end: ISODate;
}

export interface Job extends JobCreate {
  id: UUID;
  region_id: UUID;
  region_name: string;
  status: JobStatus;
  stage: string;
  progress: number;
  trigger: string;
  error: string | null;
  created_at: ISODateTime;
  started_at: ISODateTime | null;
  finished_at: ISODateTime | null;
  result_id: UUID | null;
  detector: string | null;
}

export interface ModelVersion {
  id: UUID;
  detector_id: string;
  version: string;
  kind: "rule-based" | "deep-learning";
  metrics: Record<string, unknown>;
  created_at: ISODateTime;
}

export interface Evidence {
  reference_url: string;
  observation_url: string;
  overlay_url: string;
  /** TL, TR, BR, BL en lon/lat */
  corners: [LonLat, LonLat, LonLat, LonLat];
  bounds: BBox;
}

export interface Result {
  id: UUID;
  job_id: UUID;
  region_id: UUID;
  quality_ok: boolean;
  quality_notes: string[];
  analysed_area_ha: number;
  changed_area_ha: number;
  reference_valid_fraction: number;
  observation_valid_fraction: number;
  reference_first: ISODateTime;
  reference_last: ISODateTime;
  observation_first: ISODateTime;
  observation_last: ISODateTime;
  created_at: ISODateTime;
  model: ModelVersion;
  evidence: Evidence | null;
  polygon_count: number;
  scenes: Scene[];
}

export interface Explanation {
  headline: string;
  summary: string;
  area_text: string;
  confidence_text: string;
  caveat: string;
}

export interface Alert {
  id: UUID;
  code: string;
  region_id: UUID;
  region_name: string;
  territory_slug: string;
  territory_name: string;
  status: AlertStatus;
  severity: Severity;
  signal: ChangeSignal;
  confidence: number;
  area_ha: number;
  centroid: LonLat;
  reference_date: ISODateTime;
  observation_date: ISODateTime;
  first_detected_at: ISODateTime;
  last_detected_at: ISODateTime;
  detection_count: number;
  image_quality: number;
  detector: string;
  detector_kind: "rule-based" | "deep-learning";
  explanation: Explanation;
}

export interface AlertEvent {
  id: UUID;
  type: "created" | "redetected" | "status_changed" | "comment" | "notified";
  from_status: AlertStatus | null;
  to_status: AlertStatus | null;
  comment: string | null;
  actor_name: string | null;
  created_at: ISODateTime;
}

export interface AlertDetail extends Alert {
  geometry: GeoJSONGeometry;
  source: string;
  evidence: Evidence | null;
  result_id: UUID;
  mean_ndvi_drop: number | null;
  mean_nbr_drop: number | null;
  events: AlertEvent[];
  allowed_transitions: AlertStatus[];
}

export interface AlertFilters {
  status?: AlertStatus[];
  severity?: Severity[];
  territory?: string;
  region_id?: UUID;
  date_from?: ISODate;
  date_to?: ISODate;
  bbox?: BBox;
}

export interface Overview {
  monitored_area_km2: number;
  region_count: number;
  active_region_count: number;
  changed_area_ha: number;
  alerts_pending: number;
  alerts_confirmed: number;
  alerts_total: number;
  images_processed: number;
  jobs_running: number;
  last_update: ISODateTime | null;
  by_severity: Partial<Record<Severity, number>>;
  by_territory: { slug: string; name: string; regions: number; open_alerts: number; alert_area_ha: number }[];
  monthly_changed_ha: { month: string; changed_ha: number }[];
}

export interface Preferences {
  notify_email: string | null;
  notifications_enabled: boolean;
  min_severity: Severity;
  frequency: NotificationFrequency;
  region_ids: UUID[];
  signals: ChangeSignal[];
  effective_email?: string;
}

export interface NotificationItem {
  id: UUID;
  kind: "alert" | "digest" | "report" | "password_reset";
  status: "pending" | "sent" | "failed" | "skipped";
  subject: string;
  to_email: string;
  created_at: ISODateTime;
  sent_at: ISODateTime | null;
  alert_id: UUID | null;
}

export interface Report {
  id: UUID;
  format: ReportFormat;
  title: string;
  filters: Record<string, unknown>;
  size_bytes: number;
  alert_count: number;
  created_at: ISODateTime;
  download_url: string;
}

export interface PrivacyInfo {
  controller_name: string;
  controller_id: string;
  contact_email: string;
  policy_version: string;
}

export interface Source {
  slug: string;
  name: string;
  provider: string;
  collection: string;
  license: string;
  requires_credentials: boolean;
  enabled: boolean;
  notes: string;
}

export interface AuditEntry {
  id: UUID;
  actor_id: UUID | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown>;
  created_at: ISODateTime;
}
