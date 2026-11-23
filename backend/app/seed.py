"""Datos de referencia idempotentes: los cuatro territorios del alcance, sus
zonas de monitoreo iniciales, las fuentes satelitales y (opcional) el primer admin.

Aquí nunca se siembran detecciones, alertas ni estadísticas — eso solo sale
de ejecuciones reales del pipeline.

    python -m app.seed
"""

from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging, log
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import MonitoredRegion, SatelliteSource, Territory, User, UserPreferences
from app.models.enums import Role
from app.services.geo import area_km2, as_multipolygon, to_db

TERRITORIES_FILE = Path(__file__).parent / "seed" / "territories.geojson"

SOURCES = [
    {
        "slug": "earth-search-s2-c1",
        "name": "Sentinel-2 L2A Collection-1",
        "provider": "ESA Copernicus · distribuido por Element 84 Earth Search (AWS Open Data)",
        "collection": "sentinel-2-c1-l2a",
        "catalog_url": "https://earth-search.aws.element84.com/v1",
        "license": "Copernicus Sentinel Data Terms (uso libre con atribución)",
        "requires_credentials": False,
        "enabled": True,
        "notes": "Fuente principal. Reprocesamiento homogéneo de ESA; 10 m (visible/NIR) y 20 m (SWIR). Cobertura incompleta en 2022 para algunas zonas.",
    },
    {
        "slug": "earth-search-s2-legacy",
        "name": "Sentinel-2 L2A (colección heredada)",
        "provider": "ESA Copernicus · distribuido por Element 84 Earth Search (AWS Open Data)",
        "collection": "sentinel-2-l2a",
        "catalog_url": "https://earth-search.aws.element84.com/v1",
        "license": "Copernicus Sentinel Data Terms (uso libre con atribución)",
        "requires_credentials": False,
        "enabled": True,
        "notes": "Respaldo solo cuando un periodo no tiene Collection-1. Mezcla líneas base de procesamiento; se deduplica por adquisición y se marca en las notas de calidad.",
    },
    {
        "slug": "copernicus-s1-grd",
        "name": "Sentinel-1 GRD (radar)",
        "provider": "Copernicus Data Space Ecosystem",
        "collection": "SENTINEL-1",
        "catalog_url": "https://catalogue.dataspace.copernicus.eu/stac",
        "license": "Copernicus Sentinel Data Terms",
        "requires_credentials": True,
        "enabled": False,
        "notes": "No integrado aún. Útil con nubosidad persistente (Amazonía). Requiere cuenta CDSE y procesamiento SAR (calibración, speckle). Ver SATELLITE_PIPELINE.md §6.",
    },
    {
        "slug": "nasa-hls-landsat",
        "name": "Landsat 8/9 · HLS",
        "provider": "NASA Earthdata (LP DAAC)",
        "collection": "HLSL30.v2.0",
        "catalog_url": "https://cmr.earthdata.nasa.gov/stac/LPCLOUD",
        "license": "Datos abiertos NASA",
        "requires_credentials": True,
        "enabled": False,
        "notes": "No integrado aún. Aporta histórico previo a 2017 (30 m). Requiere cuenta Earthdata Login. Ver SATELLITE_PIPELINE.md §6.",
    },
]


def seed_territories(db: Session) -> int:
    fc = json.loads(TERRITORIES_FILE.read_text(encoding="utf-8"))
    created = 0
    for feat in fc["features"]:
        p = feat["properties"]
        territory = db.scalar(select(Territory).where(Territory.slug == p["slug"]))
        if territory is None:
            geom = as_multipolygon(shape(feat["geometry"]))
            territory = Territory(
                slug=p["slug"],
                name=p["name"],
                kind=p["kind"],
                description=p["description"],
                geom=to_db(geom),
                area_km2=round(area_km2(geom), 1),
                source=p["source"],
                license=p["license"],
                attribution=p["attribution"],
            )
            db.add(territory)
            db.flush()
            created += 1
        zone = p.get("starter_zone")
        if zone and not db.scalar(
            select(MonitoredRegion.id).where(MonitoredRegion.territory_id == territory.id, MonitoredRegion.name == zone["name"])
        ):
            zgeom = as_multipolygon(shape(zone["geometry"]))
            db.add(
                MonitoredRegion(
                    territory_id=territory.id,
                    name=zone["name"],
                    description=zone["note"],
                    geom=to_db(zgeom),
                    area_km2=area_km2(zgeom),
                    cadence_days=30,
                    is_active=True,
                )
            )
    return created


def seed_sources(db: Session) -> None:
    for data in SOURCES:
        src = db.scalar(select(SatelliteSource).where(SatelliteSource.slug == data["slug"]))
        if src is None:
            db.add(SatelliteSource(**data))
        else:
            for k, v in data.items():
                setattr(src, k, v)


def seed_admin(db: Session) -> None:
    s = get_settings()
    if not s.bootstrap_admin_email or not s.bootstrap_admin_password or "CHANGE_ME" in s.bootstrap_admin_password:
        return
    if db.scalar(select(User.id).where(User.role == Role.ADMIN)):
        return
    if len(s.bootstrap_admin_password) < 12:
        raise ValueError("BOOTSTRAP_ADMIN_PASSWORD must have at least 12 characters")
    admin = User(
        email=s.bootstrap_admin_email.lower(),
        full_name="Administración",
        password_hash=hash_password(s.bootstrap_admin_password),
        role=Role.ADMIN,
    )
    admin.preferences = UserPreferences()
    db.add(admin)
    log.info("bootstrap_admin_created", email=admin.email)


def main() -> None:
    configure_logging(json=False)
    with get_sessionmaker()() as db:
        n = seed_territories(db)
        seed_sources(db)
        seed_admin(db)
        db.commit()
    log.info("seed_complete", territories_created=n)


if __name__ == "__main__":
    main()
