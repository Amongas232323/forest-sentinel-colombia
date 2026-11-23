"use client";

import { DocPage, DocSection } from "@/components/layout/DocPage";
import { usePrivacyInfo } from "@/lib/api/hooks";

const TOC = [
  ["responsable", "Responsable"],
  ["datos", "Datos que tratamos"],
  ["finalidades", "Finalidades"],
  ["geografica", "Información geográfica"],
  ["terceros", "Terceros y transferencias"],
  ["conservacion", "Conservación"],
  ["derechos", "Tus derechos"],
  ["procedimiento", "Consultas y reclamos"],
  ["seguridad", "Seguridad"],
  ["cambios", "Cambios"],
].map(([id, label]) => ({ id: id!, label: label! }));

export default function PrivacyPage() {
  const { data: info } = usePrivacyInfo();
  const controller = info?.controller_name ?? "la entidad responsable configurada para esta instalación";
  const contact = info?.contact_email ?? "el correo de privacidad configurado";
  return (
    <DocPage
      eyebrow={`Política de tratamiento de datos · versión ${info?.policy_version ?? "—"}`}
      title={<>Tus datos, <span>con reglas claras.</span></>}
      intro={
        <p>
          Esta política explica cómo Forest Sentinel trata los datos personales de quienes usan la plataforma, conforme a la Ley Estatutaria 1581
          de 2012 y el Decreto 1074 de 2015 (Capítulo 25). Es un documento de referencia: cada entidad que despliegue la plataforma debe revisarlo
          con su asesoría jurídica y completarlo con sus datos.
        </p>
      }
      toc={TOC}
    >
      <DocSection id="responsable" title="Responsable del tratamiento">
        <p><strong>{controller}</strong>{info?.controller_id ? ` (identificación: ${info.controller_id})` : ""}.</p>
        <p>Canal de atención para asuntos de datos personales: <a href={`mailto:${contact}`}>{contact}</a>.</p>
      </DocSection>
      <DocSection id="datos" title="Datos que tratamos">
        <ul>
          <li><strong>Cuenta:</strong> nombre, correo electrónico, contraseña (guardada solo como hash Argon2id; nunca la conocemos), rol y fechas de acceso.</li>
          <li><strong>Notificaciones:</strong> correo de destino opcional, zonas de interés, frecuencia y registro de envíos.</li>
          <li><strong>Seguridad y auditoría:</strong> acciones realizadas (por ejemplo, revisar una alerta), con la dirección IP seudonimizada mediante hash y el navegador usado.</li>
          <li><strong>Consentimiento de cookies:</strong> tu elección, la versión de la política y un identificador aleatorio que no te identifica directamente.</li>
        </ul>
        <p>No recopilamos datos sensibles ni datos de niñas, niños o adolescentes. La plataforma no está dirigida a menores de edad.</p>
      </DocSection>
      <DocSection id="finalidades" title="Finalidades">
        <ul>
          <li>Crear y administrar tu cuenta y sus permisos.</li>
          <li>Enviarte las notificaciones e informes que tú actives o solicites.</li>
          <li>Proteger la plataforma: detectar accesos indebidos, bloquear ataques de fuerza bruta y mantener un historial auditable de decisiones sobre las alertas.</li>
          <li>Cumplir obligaciones legales y atender requerimientos de autoridades competentes.</li>
        </ul>
        <p>No vendemos ni cedemos tus datos con fines comerciales ni publicitarios.</p>
      </DocSection>
      <DocSection id="geografica" title="Información geográfica">
        <p>
          La ubicación de un bosque monitoreado <strong>no es, por sí misma, un dato personal</strong>. Sin embargo, un hallazgo puede llegar a
          asociarse con un predio y, a través de él, con una persona. Por eso: (1) la plataforma no almacena información de propietarios ni de
          catastro; (2) el acceso a las alertas exige una cuenta y queda registrado; (3) una alerta es una señal técnica que requiere verificación y
          no debe usarse para señalar a personas sin un proceso adecuado.
        </p>
      </DocSection>
      <DocSection id="terceros" title="Terceros y transferencias">
        <ul>
          <li><strong>Correo electrónico:</strong> el proveedor SMTP que configure el responsable recibe tu dirección y el contenido del mensaje para entregarlo.</li>
          <li><strong>Mapas e imágenes:</strong> tu navegador descarga teselas de OpenFreeMap, EOX (mosaico Sentinel-2) y AWS (elevación). Esos servicios reciben tu dirección IP como en cualquier descarga web; no les enviamos tu identidad ni tus búsquedas.</li>
          <li><strong>Catálogo satelital:</strong> el servidor consulta Earth Search (AWS). Esa consulta no contiene datos personales.</li>
        </ul>
        <p>Si algún proveedor está fuera de Colombia, la transferencia se realiza con las garantías exigidas por la Ley 1581 de 2012 y las instrucciones de la Superintendencia de Industria y Comercio.</p>
      </DocSection>
      <DocSection id="conservacion" title="Conservación">
        <ul>
          <li>Datos de cuenta: mientras la cuenta esté activa y hasta 2 años después de su cierre, salvo obligación legal distinta.</li>
          <li>Sesiones: el token de renovación caduca a los 14 días; los registros revocados se depuran periódicamente.</li>
          <li>Registros de auditoría y de consentimiento: 5 años, como prueba del cumplimiento.</li>
        </ul>
      </DocSection>
      <DocSection id="derechos" title="Tus derechos">
        <p>Como titular puedes: conocer, actualizar y rectificar tus datos; solicitar prueba de la autorización; ser informado del uso que se les da; revocar la autorización o pedir la supresión cuando no exista un deber legal de conservarlos; acceder gratuitamente a ellos; y presentar quejas ante la Superintendencia de Industria y Comercio después de agotar el trámite con el responsable.</p>
      </DocSection>
      <DocSection id="procedimiento" title="Consultas y reclamos">
        <ul>
          <li><strong>Consultas:</strong> se responden en máximo 10 días hábiles, prorrogables 5 días hábiles más informando el motivo.</li>
          <li><strong>Reclamos</strong> (corrección, actualización, supresión o incumplimiento): se atienden en máximo 15 días hábiles, prorrogables 8 días hábiles más. Si el reclamo está incompleto te pediremos completarlo dentro de los 5 días siguientes.</li>
          <li>Escribe a <a href={`mailto:${contact}`}>{contact}</a> indicando tu nombre, el correo de tu cuenta, la descripción de la solicitud y los documentos que quieras aportar.</li>
        </ul>
      </DocSection>
      <DocSection id="seguridad" title="Seguridad">
        <p>Aplicamos cifrado en tránsito (HTTPS en producción), contraseñas con Argon2id, sesiones de corta duración con rotación, control de permisos en el servidor, limitación de intentos y registros de auditoría. Ningún sistema es infalible: si detectamos un incidente que afecte tus datos te informaremos y lo reportaremos según la ley.</p>
      </DocSection>
      <DocSection id="cambios" title="Cambios a esta política">
        <p>Publicaremos cualquier cambio sustancial en esta página con una nueva versión y, si afecta las finalidades, pediremos de nuevo tu autorización.</p>
      </DocSection>
    </DocPage>
  );
}
