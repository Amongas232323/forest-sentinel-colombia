# Privacidad y tratamiento de datos

Marco: **Ley Estatutaria 1581 de 2012**, **Decreto 1074 de 2015** (Libro 2, Parte 2, Título 2, Capítulo 25 — antes Decreto 1377 de 2013) e instrucciones de la Superintendencia de Industria y Comercio. La política pública está en `/privacy` (frontend) y se alimenta de las variables `PRIVACY_CONTROLLER_*`.

> Este documento y la política incluida son una **base técnica**, no una garantía automática de cumplimiento. Cada entidad que despliegue Forest Sentinel debe validarlos con su asesoría jurídica, inscribir sus bases de datos en el RNBD si le aplica y designar el área responsable de atender a los titulares.

## 1. Inventario de datos personales

| Dato | Dónde | Finalidad | Base | Retención |
|---|---|---|---|---|
| Nombre, correo, rol | `users` | Cuenta y permisos | Autorización expresa al registrarse (casilla no premarcada, versión guardada) | Cuenta activa + 2 años |
| Hash de contraseña (Argon2id) | `users` | Autenticación | Necesario para el servicio | Igual que la cuenta |
| Correo de notificación, zonas, frecuencia | `user_preferences` | Enviar avisos que el usuario activa | Autorización (opt-in) | Hasta que se desactive o se elimine la cuenta |
| Registro de envíos | `notifications` | Trazabilidad, evitar duplicados | Interés legítimo / prueba | 2 años |
| IP seudonimizada (HMAC), navegador | `auth_sessions`, `audit_logs`, `cookie_consents` | Seguridad, auditoría, prueba de consentimiento | Interés legítimo / obligación de prueba (art. 9 Ley 1581) | 5 años (auditoría y consentimiento) |
| Identificador aleatorio de consentimiento | `cookie_consents`, `localStorage` | Recordar y probar la elección | Necesario | Hasta cambio de política |

No se tratan datos sensibles ni de menores. No hay perfiles publicitarios ni venta de datos.

## 2. Información geográfica

La ubicación de un bosque no es un dato personal por sí misma. Puede volverse uno si se asocia con un predio y su propietario. Medidas:

- No se almacenan datos catastrales ni de propietarios.
- Las alertas solo son visibles para usuarios autenticados y cada acceso a acciones sensibles queda auditado.
- Las alertas se presentan como **señales técnicas a verificar**, con advertencias explícitas para evitar señalamientos indebidos.
- Los informes exportados contienen coordenadas: su distribución es responsabilidad de quien los envía (queda registro del envío).

## 3. Cookies y almacenamiento local

| Nombre | Tipo | Categoría | Antes del consentimiento |
|---|---|---|---|
| `fs_refresh` | Cookie httpOnly | Necesaria | Solo al iniciar sesión |
| `fs_consent` | localStorage | Necesaria | Se escribe al decidir |
| `fs_ui` | localStorage | Funcional | **Nunca** sin consentimiento (`uiStorage` es no-op) |
| — | — | Analítica | No se usa ninguna herramienta; la categoría existe para bloquear futuras |

Banner con **Aceptar todas / Rechazar opcionales / Configurar**, casillas **no premarcadas**, preferencias modificables desde el pie de página, `/cookies` y Configuración. Cada decisión se registra en el servidor (`POST /privacy/consent`) con versión de política e IP seudonimizada.

## 4. Terceros

| Tercero | Datos que recibe | Motivo |
|---|---|---|
| Proveedor SMTP (configurable) | Correo del destinatario y contenido | Entregar notificaciones |
| OpenFreeMap, EOX, AWS (teselas) | IP del navegador al descargar teselas | Mostrar mapas y relieve |
| Earth Search / AWS (servidor) | Coordenadas de la zona (no personales) | Buscar y leer imágenes |

Si algún proveedor está fuera de Colombia, la transferencia debe ampararse en los supuestos del art. 26 de la Ley 1581 o en las garantías definidas por la SIC.

## 5. Derechos de los titulares y procedimiento

Conocer, actualizar, rectificar, solicitar prueba de la autorización, ser informado del uso, revocar/suprimir (salvo deber legal), acceder gratuitamente y quejarse ante la SIC. **Consultas: 10 días hábiles** (+5). **Reclamos: 15 días hábiles** (+8), con requerimiento de completitud en 5 días. Canal: `PRIVACY_CONTACT_EMAIL`.

Soporte técnico para atenderlos: un administrador puede desactivar la cuenta (revoca sesiones); la supresión definitiva se realiza eliminando el usuario (las alertas conservan su historial con el actor anonimizado por `ON DELETE SET NULL`).

## 6. Otras jurisdicciones

Si se usa con personas en la UE/EEE aplicaría además el RGPD (bases jurídicas, DPO si corresponde, derecho de portabilidad, registro de actividades). El diseño actual (minimización, seudonimización, consentimiento granular y probado) facilita esa adecuación.
