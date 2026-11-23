"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { TextAreaField } from "@/components/ui/Field";
import { toast } from "@/components/ui/Feedback";
import { ApiError } from "@/lib/api/client";
import { useAddComment, useUpdateAlertStatus } from "@/lib/api/hooks";
import type { AlertDetail, AlertStatus } from "@/lib/api/types";
import { STATUS, STATUS_ACTIONS } from "@/lib/format";

const NEEDS_COMMENT: AlertStatus[] = ["confirmed", "dismissed"];

export function ReviewPanel({ alert, canReview }: { alert: AlertDetail; canReview: boolean }) {
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string>();
  const update = useUpdateAlertStatus(alert.id);
  const addComment = useAddComment(alert.id);

  async function transition(status: AlertStatus) {
    if (NEEDS_COMMENT.includes(status) && !comment.trim()) {
      setError("Escribe una observación que explique tu decisión.");
      return;
    }
    setError(undefined);
    try {
      await update.mutateAsync({ status, comment: comment.trim() || undefined });
      setComment("");
      toast.success(`Estado actualizado: ${STATUS[status].label}.`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo actualizar el estado.");
    }
  }

  async function saveComment() {
    if (!comment.trim()) return setError("Escribe una observación.");
    try {
      await addComment.mutateAsync(comment.trim());
      setComment("");
      setError(undefined);
      toast.success("Observación guardada.");
    } catch {
      toast.error("No se pudo guardar la observación.");
    }
  }

  if (!canReview)
    return (
      <div className="border-t border-ink pt-4 text-sm text-ink-2">
        <p className="eyebrow mb-2">Revisión</p>
        Tu rol es de observación. Un analista puede confirmar o descartar este hallazgo.
      </div>
    );

  return (
    <section aria-labelledby="review-title" className="flex flex-col gap-4 border-2 border-ink bg-field p-5">
      <div>
        <p className="eyebrow mb-1">Revisión humana</p>
        <h2 id="review-title" className="font-display text-h4 font-medium text-ink">¿Qué concluyes?</h2>
        <p className="mt-1 text-sm text-ink-2">Estado actual: <strong className="text-ink">{STATUS[alert.status].label}</strong>. {STATUS[alert.status].hint}</p>
      </div>
      <TextAreaField
        label="Observación"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        maxLength={4000}
        placeholder="Ej.: verificado con imagen de alta resolución; se observa apertura de potrero."
        hint="Obligatoria para confirmar o descartar. Queda en el historial."
        error={error}
      />
      <div className="flex flex-wrap gap-2">
        {alert.allowed_transitions.map((s) => (
          <Button key={s} size="sm" variant={s === "confirmed" ? "primary" : s === "dismissed" ? "danger" : "secondary"} onClick={() => transition(s)} loading={update.isPending && update.variables?.status === s}>
            {STATUS_ACTIONS[s]}
          </Button>
        ))}
        <Button size="sm" variant="ghost" onClick={saveComment} loading={addComment.isPending}>
          Solo guardar observación
        </Button>
      </div>
    </section>
  );
}
