/**
 * Compatibilidad del contrato: todo campo que lee la UI tiene que existir en el schema
 * OpenAPI del backend (contracts/openapi.json, lo exporta backend/scripts/export_contracts.py).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const spec = JSON.parse(readFileSync(resolve(__dirname, "../../../contracts/openapi.json"), "utf-8")) as {
  components: { schemas: Record<string, { properties?: Record<string, unknown> }> };
};

// Mantener sincronizado con src/lib/api/types.ts (las interfaces de TS solo existen en compilación).
const CONSUMED: Record<string, string[]> = {
  AlertOut: ["id", "code", "region_id", "region_name", "territory_slug", "territory_name", "status", "severity", "signal", "confidence", "area_ha", "centroid", "reference_date", "observation_date", "first_detected_at", "last_detected_at", "detection_count", "image_quality", "detector", "detector_kind", "explanation"],
  AlertDetail: ["geometry", "source", "evidence", "result_id", "mean_ndvi_drop", "mean_nbr_drop", "events", "allowed_transitions"],
  Explanation: ["headline", "summary", "area_text", "confidence_text", "caveat"],
  RegionOut: ["id", "territory_slug", "territory_name", "name", "area_km2", "is_active", "cadence_days", "last_run_at", "centroid", "bbox", "geometry", "open_alerts", "last_job_status"],
  JobOut: ["id", "region_id", "region_name", "status", "stage", "progress", "reference_start", "observation_end", "error", "result_id", "detector"],
  ResultOut: ["quality_ok", "quality_notes", "analysed_area_ha", "changed_area_ha", "reference_valid_fraction", "observation_valid_fraction", "model", "evidence", "polygon_count", "scenes"],
  EvidenceOut: ["reference_url", "observation_url", "overlay_url", "corners", "bounds"],
  OverviewOut: ["monitored_area_km2", "region_count", "active_region_count", "changed_area_ha", "alerts_pending", "alerts_confirmed", "images_processed", "jobs_running", "last_update", "by_territory", "monthly_changed_ha"],
  PreferencesOut: ["notify_email", "notifications_enabled", "min_severity", "frequency", "region_ids", "signals", "effective_email"],
  TokenOut: ["access_token", "expires_in", "user"],
  UserOut: ["id", "email", "full_name", "role", "is_active", "created_at", "last_login_at"],
};

describe("frontend ↔ backend contract", () => {
  for (const [schema, fields] of Object.entries(CONSUMED)) {
    it(`${schema} exposes every field the UI reads`, () => {
      const props = Object.keys(spec.components.schemas[schema]?.properties ?? {});
      expect(props.length, `${schema} missing from OpenAPI`).toBeGreaterThan(0);
      expect(fields.filter((f) => !props.includes(f))).toEqual([]);
    });
  }
});
