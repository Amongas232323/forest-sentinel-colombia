/**
 * Tokens de movimiento de la casa (basados en la charla de Apple "Designing Fluid Interfaces").
 * Los resortes se describen con bounce (≈ 1 − razón de amortiguamiento) y duración (≈ respuesta).
 */

/** Resorte por defecto de la UI: amortiguamiento crítico (sin sobrepaso), respuesta ≈ 0.35 s. */
export const SPRING = { type: "spring", bounce: 0, duration: 0.35 } as const;

/** Solo después de un gesto que llevaba momentum (flick / soltar un arrastre): amortiguamiento ≈ 0.8. */
export const SPRING_MOMENTUM = { type: "spring", bounce: 0.2, duration: 0.3 } as const;

/** Proyección de momentum de Apple: dónde quedaría quieto un flick (px). */
export function project(velocity: number, decelerationRate = 0.998): number {
  return ((velocity / 1000) * decelerationRate) / (1 - decelerationRate);
}
