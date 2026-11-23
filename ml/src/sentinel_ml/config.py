"""Umbrales del pipeline, centralizados y documentados.

Cada valor de aquí es un *parámetro de operación heurístico*, no una constante
científica. Los dejamos expuestos para que los analistas los ajusten según el bioma; ver
docs/AI_MODEL_DOCUMENTATION.md para entender por qué elegimos los valores por defecto.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SpectralThresholds:
    # El píxel tiene que haber sido vegetación densa en el periodo de referencia.
    min_reference_ndvi: float = 0.60
    # Caída mínima de NDVI entre periodos para que cuente como pérdida.
    min_ndvi_drop: float = 0.20
    # Caída mínima de NBR; el NBR es más sensible a la remoción del dosel y al fuego.
    min_nbr_drop: float = 0.15
    # Valores con los que escalamos las caídas a un puntaje de cambio de 0..1.
    ndvi_drop_saturation: float = 0.50
    nbr_drop_saturation: float = 0.60
    # Si el NBR después del evento queda por debajo de esto, sugiere quema más que tala.
    burn_nbr_post_max: float = -0.05
    # Si el NDWI después del evento queda por encima de esto, sugiere inundación / agua.
    water_ndwi_post_min: float = 0.10


@dataclass(frozen=True)
class QualityThresholds:
    # Fracción mínima de píxeles válidos (sin nube/sombra) en AMBOS compuestos
    # para que una ejecución pueda generar alertas.
    min_valid_fraction: float = 0.40
    max_scene_cloud_cover: float = 60.0


@dataclass(frozen=True)
class VectorThresholds:
    # Unidad mínima de mapeo en hectáreas (0.5 ha ≈ 50 píxeles a 10 m).
    min_area_ha: float = 0.5
    # Tolerancia de Douglas–Peucker en metros.
    simplify_tolerance_m: float = 10.0
    # Umbral de probabilidad que usamos para binarizar el puntaje de cambio.
    score_threshold: float = 0.5


@dataclass(frozen=True)
class SeverityThresholds:
    """Niveles operativos — documentados en AI_MODEL_DOCUMENTATION.md.

    Un hallazgo se clasifica en el nivel *más alto* cuyos requisitos de área Y
    de puntaje cumpla.
    """

    moderate_area_ha: float = 1.0
    moderate_score: float = 0.55
    high_area_ha: float = 3.0
    high_score: float = 0.65
    priority_area_ha: float = 10.0
    priority_score: float = 0.75


@dataclass(frozen=True)
class PipelineLimits:
    # Topes duros que protegen la RAM y los hosts remotos (seguridad: abuso de recursos).
    max_aoi_km2: float = 2500.0
    max_pixels_per_side: int = 8192
    tile_size: int = 1024
    max_scenes_per_period: int = 4
    resolution_m: float = 10.0
    http_timeout_s: int = 60


@dataclass(frozen=True)
class PipelineConfig:
    spectral: SpectralThresholds = field(default_factory=SpectralThresholds)
    quality: QualityThresholds = field(default_factory=QualityThresholds)
    vector: VectorThresholds = field(default_factory=VectorThresholds)
    severity: SeverityThresholds = field(default_factory=SeverityThresholds)
    limits: PipelineLimits = field(default_factory=PipelineLimits)


DEFAULT_CONFIG = PipelineConfig()

# El pipeline solo puede leer de estos hosts (protección contra SSRF). Los items de STAC
# son entrada no confiable: un catálogo malicioso podría apuntar los assets a cualquier lado.
ALLOWED_ASSET_HOSTS: frozenset[str] = frozenset(
    {
        "sentinel-cogs.s3.us-west-2.amazonaws.com",
        "e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com",
    }
)

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"
# Collection-1 es el reprocesamiento homogéneo de la ESA (radiometría consistente entre
# años) y es la que preferimos. La colección legacy mezcla baselines de procesamiento y,
# en los items reprocesados "_1_", declara offsets que no coinciden con los datos.
S2_COLLECTION_C1 = "sentinel-2-c1-l2a"
S2_COLLECTION_LEGACY = "sentinel-2-l2a"
