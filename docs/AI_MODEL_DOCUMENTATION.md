# Inteligencia artificial y detección de cambios

## 1. Principios

1. **No simular IA.** Cada resultado registra qué detector lo produjo (`model_versions.kind = rule-based | deep-learning`) y la interfaz lo muestra («REGLAS ESPECTRALES» o «MODELO IA») junto con la frase «no es una probabilidad calibrada».
2. **Pérdida de vegetación ≠ deforestación.** El sistema detecta *cambios*; la confirmación es humana (`alerts.status = confirmed` exige observación escrita).
3. **Métricas sobre territorio no visto.** Toda métrica reportada proviene de un conjunto de prueba **geográficamente separado** del entrenamiento.

## 2. Detectores disponibles

| ID | Tipo | Estado | Cuándo se usa |
|---|---|---|---|
| `spectral-baseline@1.0.0` | Reglas espectrales | **Producción** | Por defecto (`MODEL_CHECKPOINT` vacío) |
| `siamese-unet@0.1.0` | Red neuronal (PyTorch) | Experimental, evaluado (§7) | Solo si `MODEL_CHECKPOINT` apunta a un checkpoint aprobado |

Ambos implementan el mismo contrato (`detectors/base.py`), así que el resto del sistema no cambia al pasar de uno a otro.

## 3. Detector espectral (baseline)

Entrada: composiciones de mediana (6 bandas: azul, verde, rojo, NIR, SWIR1, SWIR2) y máscara de validez.

| Paso | Regla (configurable en `config.SpectralThresholds`) |
|---|---|
| Elegibilidad | `NDVI_ref ≥ 0,60` (era vegetación densa) |
| Evidencia | `ΔNDVI ≥ 0,20` **y** `ΔNBR ≥ 0,15` |
| Intensidad | `0,5·min(ΔNDVI/0,50, 1) + 0,5·min(ΔNBR/0,60, 1)`; mediana 3×3 |
| Señal sugerida | `NBR_obs ≤ −0,05` → posible quema; `NDWI_obs ≥ 0,10` → posible agua; si no, pérdida de vegetación |

Justificación: NDVI responde al verdor, NBR (NIR/SWIR2) a la estructura del dosel y al fuego; exigir ambas caídas reduce falsos positivos por sequía estacional (que afecta sobre todo a NDVI). La condición de elegibilidad evita marcar cultivos o pastos que «pierden verde» (prueba `test_spectral_detector_ignores_pixels_that_were_not_forest`). Los índices **no sustituyen** a un modelo: son el *baseline* contra el que se compara cualquier modelo.

## 4. Modelo de segmentación: Siamese U-Net (FC-Siam-diff)

```
ref ─► Encoder (compartido) ─┐ f_ref¹…f_ref⁴
obs ─► Encoder (compartido) ─┤ f_obs¹…f_obs⁴
                             └► |f_obs − f_ref| en cada escala (saltos)
bottleneck = concat(f_obs⁴, |Δ⁴|) → 3 bloques de decodificación (ConvTranspose + 2×Conv-BN-ReLU) → 1×1 → logit de cambio
anchos (16, 32, 64, 128) · dropout 0,1 · ~1,4 M parámetros
```

| Arquitectura | Ventajas | Por qué no (por ahora) |
|---|---|---|
| **FC-Siam-diff (elegida)** | Hecha para cambio bitemporal multiespectral (Daudt et al., ICIP 2018); pesos compartidos = regularización con pocos datos; ligera | — |
| U-Net++ | Mejor detalle de bordes | Más parámetros/memoria; no modela explícitamente la diferencia temporal |
| DeepLabV3+ | Contexto multiescala (ASPP) | Backbones preentrenados en RGB; pierde resolución en cambios pequeños (< 1 ha) |
| SegFormer | Estado del arte en segmentación semántica | Requiere muchos datos o preentrenamiento multiespectral; costoso en CPU |

Inferencia: parches de 256 px con solape de 64 y mezcla con ventana de Hann (sin costuras). El umbral elegido en validación se reasigna a 0,5 para que el resto del pipeline sea idéntico al del baseline.

## 5. Datos de entrenamiento (etiquetas débiles reales)

- **Imágenes:** composiciones Sentinel-2 L2A C1 de dos temporadas secas — referencia `2022-12-01/2023-03-15`, observación `2023-12-01/2024-03-15` — producidas con el **mismo código** que producción (`composite.py`).
- **Etiquetas:** Hansen et al., *Global Forest Change 2000–2024 v1.12* (`lossyear`, 30 m, CC BY 4.0), remuestreadas por vecino más cercano a la rejilla de 10 m.
  - `1` = pérdida en 2023 · `255` (ignorar) = pérdida en 2024 (fecha ambigua respecto a la composición de observación) o píxel nublado · `0` = resto.
- **AOI** (`ml/training/aois.json`, 15 × 15 km): 5 de entrenamiento (Guaviare ×3, Meta-Tinigua, Caquetá-Chairá), 1 de validación (Meta-Macarena), 2 de prueba (Caquetá-San Vicente, Amazonas-Puerto Nariño, esta última con poca deforestación para medir falsos positivos).
- **Incidencia real:** la AOI `meta-tinigua` se bloqueó de forma reproducible durante la lectura remota (dos intentos de 7 min, proceso sin CPU ni conexiones activas) y fue **omitida** por el aislamiento por subproceso. El entrenamiento usó 4 AOI de entrenamiento en lugar de 5. Esto motivó los *timeouts* de lectura añadidos a `composite.py`.
- **Limitaciones de las etiquetas:** 30 m frente a 10 m (bordes imprecisos), pérdidas de enero–marzo de 2023 caen dentro de la ventana de referencia (ruido), GFC detecta pérdida de *cobertura arbórea* (incluye incendios y talas de plantaciones), y el mapa tiene su propio error de omisión/comisión. Por eso las métricas deben leerse como **concordancia con GFC**, no como exactitud absoluta.

Construcción reproducible (cada AOI en su propio proceso con *timeout* y reintento):

```bash
python -m sentinel_ml.training build --config ml/training/aois.json --out ml/datasets/gfc
python -m sentinel_ml.training train --config ml/training/aois.json --data ml/datasets/gfc \
       --out ml/checkpoints/siamese-unet-0.1.0.pt --epochs 12 --steps 60
```

Entrenamiento: AdamW (lr 1e-3, wd 1e-4, coseno), pérdida BCE ponderada (`pos_weight = min(20, neg/pos)`) + Dice, máscara de píxeles ignorados, parches 256 px muestreados 50 % sobre positivos, aumentos rot90/flip, normalización por banda con estadísticas de entrenamiento (guardadas en el checkpoint). Se conserva el mejor modelo por F1 de validación y el umbral que lo maximiza.

## 6. Niveles operativos

| Nivel | Área mínima | Intensidad mínima | Genera alerta por defecto |
|---|---|---|---|
| Cambio bajo | 0,5 ha (unidad mínima) | — | No (`ALERT_MIN_SEVERITY=moderate`) |
| Cambio moderado | 1 ha | 0,55 | Sí |
| Cambio importante | 3 ha | 0,65 | Sí |
| Hallazgo prioritario | 10 ha | 0,75 | Sí |

Configurables en `config.SeverityThresholds` (pipeline) y `ALERT_MIN_SEVERITY` (backend). La «intensidad» es **ordinal**: no se ha calibrado como probabilidad (no hay validación de campo para hacerlo).

## 7. Evaluación

Métricas a nivel de píxel con matriz de confusión global (micro-promedio, convención OSCD) sobre los píxeles no ignorados de las AOI de **prueba**. Precisión, *recall*, F1 (= Dice en binario), IoU, tasa de falsos positivos (FPR) y de falsos negativos (FNR).

<!-- RESULTS:START -->
Generado el 2026-11-12 a partir de `siamese-unet-0.1.0.metrics.json`. AOI de prueba (nunca vistas): caqueta-sanvicente, amazonas-puertonarino.

| Métrica (prueba) | Siamese U-Net | Baseline espectral |
|---|---:|---:|
| Precisión | 0.060 | 0.040 |
| Recall | 0.494 | 0.097 |
| F1 / Dice | 0.108 | 0.057 |
| IoU | 0.057 | 0.029 |
| Tasa de falsos positivos | 0.020 | 0.006 |
| Tasa de falsos negativos | 0.506 | 0.903 |
| Píxeles positivos de prueba (TP+FN) | 13,502 | 13,502 |

F1 de validación del mejor epoch: **0.258** · umbral elegido en validación: **0.85** · `pos_weight` = 20.0 · píxeles positivos de entrenamiento: 74,390.

Evolución del entrenamiento:

| Epoch | Pérdida | F1 validación | Umbral |
|---:|---:|---:|---:|
| 1 | 1.5972 | 0.055 | 0.85 |
| 2 | 1.4005 | 0.257 | 0.85 |
| 3 | 1.2512 | 0.144 | 0.85 |
| 4 | 1.1512 | 0.044 | 0.85 |
| 5 | 1.0683 | 0.137 | 0.85 |
| 6 | 0.9893 | 0.085 | 0.85 |
| 7 | 0.9226 | 0.090 | 0.85 |
| 8 | 0.8747 | 0.117 | 0.85 |
| 9 | 0.8592 | 0.114 | 0.85 |
| 10 | 0.8403 | 0.211 | 0.85 |
| 11 | 0.7975 | 0.258 | 0.85 |
| 12 | 0.7900 | 0.234 | 0.85 |

**Lectura honesta:** el modelo supera al baseline en F1 (0.108 frente a 0.057) sobre territorio no visto. Las cifras miden concordancia con Hansen GFC (etiquetas débiles a 30 m, §5), no exactitud de campo. Activar el modelo en producción requiere además validación con analistas sobre alertas reales.
<!-- RESULTS:END -->

**Decisión:** aunque el modelo duplica el F1 del baseline y multiplica por cinco el *recall*, su precisión (6 %) generaría unas 15 falsas alarmas por cada acierto. Por eso **producción sigue usando el detector espectral** (más conservador) y el modelo queda como experimental. Observaciones para la siguiente iteración:

- El umbral óptimo quedó en el tope del rango buscado (0,85): el modelo sobrepredice. El rango ya se amplió a 0,2–0,975 en `train.py`.
- La zona de validación tiene muy pocos positivos (1 318 px), así que el F1 de validación es ruidoso. Conviene usar dos AOI de validación.
- Las etiquetas GFC a 30 m y anuales limitan la concordancia alcanzable. Para pasar a producción haría falta un conjunto revisado por analistas (las alertas confirmadas o descartadas en la plataforma sirven exactamente para eso) y más AOI, incluidas zonas andinas.

## 8. Validación del pipeline con datos reales

| Prueba | Resultado |
|---|---|
| Tinigua (Meta) 2019 vs 2020, 12 332 ha | 17 polígonos, 47,7 ha; inspección visual: claros nuevos dentro del bosque, sin marcar el río ni pastos previos |
| Guaviare (Charras) 2024 vs 2025, 49 461 ha | 46 polígonos, 120,5 ha, 25 alertas; mayor hallazgo 14,9 ha (ΔNDVI 0,37, ΔNBR 0,63) visible como apertura de potrero |
| Mezcla de colecciones (`_0_` + `_1_`) | Detectado y corregido (SATELLITE_PIPELINE §2): producía composiciones con color anómalo |

## 9. Limitaciones conocidas

- Nubes persistentes: sin alternativa radar (Sentinel-1 no integrado), un periodo nublado no se analiza (se informa).
- Bosque andino y páramo (Cundinamarca, Sierra Nevada): NDVI de referencia más bajo; el umbral 0,60 puede omitir cambios. Recomendación: umbrales por territorio.
- Degradación bajo dosel y tala selectiva: poco visibles a 10 m.
- El modelo se entrenó en el arco amazónico; su desempeño en ecosistemas andinos o secos **no está evaluado**.
- Las clases semánticas (agua, agrícola, suelo) se aproximan con índices como «señal sugerida»; no hay un clasificador de cobertura entrenado.
