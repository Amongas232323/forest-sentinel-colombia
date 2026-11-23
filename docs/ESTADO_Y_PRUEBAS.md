# Estado del proyecto, pruebas y créditos

Documento de referencia que acompaña al [README](../README.md).

## Estado real

| Área | Estado | Evidencia |
|---|---|---|
| Pipeline satelital | ✅ Funcional con datos reales | Sentinel-2 L2A Collection-1 (Earth Search), lectura por ventanas, reanudable; probado en Guaviare (49 461 ha → 46 polígonos) |
| Detección | ✅ **Detector espectral por reglas** en producción | Documentado y etiquetado como «no IA» en toda la interfaz |
| Modelo de IA (Siamese U-Net) | ⚙️ Entrenado y evaluado, **experimental** | Etiquetas reales (Hansen GFC), prueba en territorio no visto: F1 0,108 frente a 0,057 del baseline, pero precisión del 6 %. No se activa en producción ([detalle](docs/AI_MODEL_DOCUMENTATION.md#7-evaluación)) |
| PostGIS / alertas | ✅ | Deduplicación espacio-temporal, puerta de calidad, recorte a la zona |
| Correo | ✅ | SMTP real verificado con Mailpit; un correo por alerta; baja con un clic |
| Frontend | ✅ | Todas las secciones conectadas a la API real; verificado en escritorio y móvil |
| Sentinel-1 / Landsat | ❌ No integrados | Registrados como fuentes «no integradas» con los requisitos documentados |
| Despliegue productivo | ⚠️ Preparado, no ejecutado | Dockerfiles, compose y guía; requiere TLS, dominio y secretos reales |

Flujo completo verificado de extremo a extremo: **Earth Search → lectura de COG → composición → detector → polígonos → PostGIS → alerta → tablero → correo SMTP**.


## Pruebas

```bash
cd ml && pytest -q                       # 30 pruebas (pipeline, detectores, modelo, entrenamiento)
cd backend && pytest -q                  # 59 pruebas (requiere el servicio db; crea <db>_test)
cd frontend && npm test                  # 25 pruebas (componentes, validación, a11y con axe, cliente API, contrato OpenAPI)
cd frontend && npm run lint && npm run typecheck && npm run build
```


## Créditos de datos

Contiene información modificada de Copernicus Sentinel (ESA). Texturas del planeta: NASA Visible Earth (dominio público). Límites: © OpenStreetMap contributors / geoBoundaries (ODbL). Elevación: AWS Terrain Tiles. Etiquetas de entrenamiento: Hansen/UMD/Google/USGS/NASA Global Forest Change (CC BY 4.0). Mapa base: OpenFreeMap.
