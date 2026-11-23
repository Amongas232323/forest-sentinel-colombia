"""Búsqueda de escenas en catálogos STAC públicos (Earth Search / Sentinel-2 L2A).

Política de colecciones (ver docs/SATELLITE_PIPELINE.md §2):

1. Consultamos Sentinel-2 Collection-1 L2A (reprocesamiento homogéneo).
2. Solo si un periodo no tiene escenas de Collection-1, caemos a la colección L2A
   legacy, dejando un solo item por adquisición (el procesamiento original ``_0_``,
   cuyos offsets declarados sí coinciden con sus píxeles). A quien llama se le avisa con
   ``SceneSearch.legacy`` para que el resultado pueda llevar una nota de calidad.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from pystac import Item
from pystac_client import Client

from .config import ALLOWED_ASSET_HOSTS, EARTH_SEARCH_URL, S2_COLLECTION_C1, S2_COLLECTION_LEGACY
from .contracts import BBox, DateWindow, SceneRef

log = logging.getLogger(__name__)

# Llaves de los assets (iguales en las dos colecciones de Earth Search) que usa el pipeline.
REQUIRED_ASSETS = ("blue", "green", "red", "nir", "swir16", "swir22", "scl")
_LEGACY_ID = re.compile(r"^(S2[ABC])_(\w{5})_(\d{8})_(\d+)_L2A$")


class UntrustedAssetError(ValueError):
    """Se lanza cuando un asset de STAC apunta por fuera de la lista permitida."""


@dataclass
class SceneSearch:
    scenes: list[SceneRef]
    collection: str
    legacy: bool


def validate_asset_href(href: str) -> str:
    parsed = urlparse(href)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_ASSET_HOSTS:
        raise UntrustedAssetError(f"asset host not allowed: {parsed.hostname!r}")
    if not parsed.path.lower().endswith(".tif"):
        raise UntrustedAssetError("only GeoTIFF/COG assets are accepted")
    return href


def _epsg_of(item: Item) -> int:
    props = item.properties
    if props.get("proj:epsg"):
        return int(props["proj:epsg"])
    code = props.get("proj:code")
    if isinstance(code, str) and code.upper().startswith("EPSG:"):
        return int(code.split(":", 1)[1])
    raise ValueError(f"item {item.id} has no projection information")


def item_to_scene(item: Item, collection: str) -> SceneRef:
    assets: dict[str, str] = {}
    for key in REQUIRED_ASSETS:
        if key not in item.assets:
            raise ValueError(f"item {item.id} lacks required asset {key}")
        asset = item.assets[key]
        assets[key] = validate_asset_href(asset.href)
        if key != "scl":
            meta = (asset.extra_fields.get("raster:bands") or [{}])[0]
            # reflectance = DN * scale + offset
            assets[f"{key}:scale"] = str(float(meta.get("scale", 0.0001)))
            assets[f"{key}:offset"] = str(float(meta.get("offset", 0.0)))
    if item.datetime is None:
        raise ValueError(f"item {item.id} has no datetime")
    return SceneRef(
        scene_id=item.id,
        source="earth-search",
        collection=collection,
        acquired_at=item.datetime,
        cloud_cover=item.properties.get("eo:cloud_cover"),
        epsg=_epsg_of(item),
        assets=assets,
        tile_id=item.properties.get("grid:code") or item.properties.get("s2:mgrs_tile"),
    )


def _acquisition_key(scene: SceneRef) -> tuple[str, str]:
    return (scene.tile_id or "", scene.acquired_at.strftime("%Y%m%d"))


def dedupe_legacy(scenes: list[SceneRef]) -> list[SceneRef]:
    """Deja un item legacy por adquisición, prefiriendo el procesamiento ``_0_``."""
    best: dict[tuple[str, str], tuple[int, SceneRef]] = {}
    for s in scenes:
        m = _LEGACY_ID.match(s.scene_id)
        processing = int(m.group(4)) if m else 99
        key = _acquisition_key(s)
        if key not in best or processing < best[key][0]:
            best[key] = (processing, s)
    return [s for _, s in best.values()]


def _query(client: Client, collection: str, bbox: BBox, window: DateWindow, max_cloud: float, limit: int) -> list[SceneRef]:
    search = client.search(
        collections=[collection],
        bbox=bbox.as_list(),
        datetime=window.as_interval(),
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=limit,
    )
    return list(_safe_convert(search.items(), collection))


def search_scenes(
    bbox: BBox,
    window: DateWindow,
    max_cloud: float,
    limit: int = 40,
    catalog_url: str = EARTH_SEARCH_URL,
) -> SceneSearch:
    """Devuelve las escenas candidatas ordenadas por cobertura de nubes (de menor a mayor)."""
    client = Client.open(catalog_url)
    scenes = _query(client, S2_COLLECTION_C1, bbox, window, max_cloud, limit)
    collection, legacy = S2_COLLECTION_C1, False
    if not scenes:
        scenes = dedupe_legacy(_query(client, S2_COLLECTION_LEGACY, bbox, window, max_cloud, limit))
        collection, legacy = S2_COLLECTION_LEGACY, True
    scenes.sort(key=lambda s: s.cloud_cover if s.cloud_cover is not None else 100.0)
    log.info("stac %s %s %s -> %d scenes", collection, bbox.as_list(), window.as_interval(), len(scenes))
    return SceneSearch(scenes, collection, legacy)


def _safe_convert(items: Iterable[Item], collection: str) -> Iterable[SceneRef]:
    for item in items:
        try:
            yield item_to_scene(item, collection)
        except (ValueError, UntrustedAssetError) as exc:
            log.warning("skipping item %s: %s", item.id, exc)
