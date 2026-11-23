import type { Metadata } from "next";
import { DocPage, DocSection } from "@/components/layout/DocPage";

export const metadata: Metadata = { title: "Metodología y ayuda" };

const TOC = [
  ["que-es", "Qué hace Forest Sentinel"],
  ["leer-alerta", "Cómo leer una alerta"],
  ["metodo", "Cómo se detectan los cambios"],
  ["niveles", "Niveles de prioridad"],
  ["limites", "Limitaciones"],
  ["glosario", "Glosario"],
  ["roles", "Roles"],
].map(([id, label]) => ({ id: id!, label: label! }));

export default function HelpPage() {
  return (
    <DocPage eyebrow="Metodología y ayuda" title={<>Cómo funciona, <span>sin letra pequeña.</span></>} toc={TOC}>
      <DocSection id="que-es" title="Qué hace Forest Sentinel">
        <p>Compara imágenes satelitales Sentinel-2 de un mismo lugar en dos periodos, identifica dónde la vegetación densa disminuyó de forma marcada, calcula el área de cada cambio y crea una alerta para que una persona la revise.</p>
        <p>Vigila cuatro territorios: <strong>Guaviare, Sierra Nevada de Santa Marta, Cundinamarca y Amazonas</strong>. Dentro de ellos se definen zonas de hasta 2.500 km².</p>
      </DocSection>
      <DocSection id="leer-alerta" title="Cómo leer una alerta">
        <ul>
          <li><strong>El titular</strong> dice qué tipo de cambio parece: pérdida de vegetación, posible quema o posible agua.</li>
          <li><strong>Las fechas</strong> son las de las imágenes comparadas, no las de la tala: el cambio ocurrió en algún momento entre ambas.</li>
          <li><strong>El área</strong> es una estimación a partir de píxeles de 10 × 10 m.</li>
          <li><strong>La intensidad</strong> indica qué tan fuerte es la señal (0 a 1). No es la probabilidad de que sea deforestación.</li>
          <li><strong>El estado</strong> muestra si alguien ya la revisó. Solo «Hallazgo confirmado» significa que una persona verificó el cambio.</li>
        </ul>
      </DocSection>
      <DocSection id="metodo" title="Cómo se detectan los cambios">
        <p>1. Para cada periodo se buscan hasta 4 imágenes Sentinel-2 L2A (Collection-1) con menos de 60 % de nubes y se combinan píxel a píxel (mediana), descartando nubes, sombras y nieve según la capa de clasificación de escena (SCL) de ESA.</p>
        <p>2. Se calculan índices espectrales: NDVI (verdor), NBR (estructura del dosel y quemas) y NDWI (agua).</p>
        <p>3. <strong>Detector actual — reglas espectrales:</strong> un píxel se marca si antes era vegetación densa (NDVI ≥ 0,60) y su NDVI cayó al menos 0,20 y su NBR al menos 0,15. La intensidad combina ambas caídas. <em>Este detector no es inteligencia artificial</em>; la plataforma incluye la arquitectura y el entrenamiento de un modelo de segmentación (Siamese U-Net) que se activa únicamente cuando existe un modelo entrenado y evaluado, y cada alerta indica qué método la produjo.</p>
        <p>4. Se eliminan píxeles aislados, se agrupan las áreas contiguas, se descartan las menores de 0,5 ha y se convierten en polígonos georreferenciados.</p>
        <p>5. Solo se crean alertas si las imágenes tienen al menos 40 % del área libre de nubes y el entorno del polígono al menos 60 %. Si un cambio se superpone con una alerta abierta de los últimos 120 días, se actualiza la existente en vez de crear otra.</p>
      </DocSection>
      <DocSection id="niveles" title="Niveles de prioridad">
        <ul>
          <li><strong>Cambio bajo:</strong> se registra pero no genera alerta por defecto.</li>
          <li><strong>Cambio moderado:</strong> ≥ 1 ha e intensidad ≥ 0,55.</li>
          <li><strong>Cambio importante:</strong> ≥ 3 ha e intensidad ≥ 0,65.</li>
          <li><strong>Hallazgo prioritario:</strong> ≥ 10 ha e intensidad ≥ 0,75.</li>
        </ul>
        <p>Los umbrales son configurables y están documentados para el equipo técnico.</p>
      </DocSection>
      <DocSection id="limites" title="Limitaciones que debes conocer">
        <ul>
          <li>Una pérdida de vegetación <strong>no siempre es deforestación</strong>: cosechas, pastos secos, cambios de temporada, quemas agrícolas o deslizamientos pueden verse igual.</li>
          <li>Las nubes persistentes (frecuentes en la Amazonía y en la Sierra Nevada) pueden impedir analizar un periodo; el sistema lo informa en vez de adivinar.</li>
          <li>La degradación bajo el dosel (tala selectiva) puede no ser visible a 10 m.</li>
          <li>En páramos y bosques andinos de Cundinamarca los umbrales pueden requerir ajuste por la menor densidad de vegetación.</li>
        </ul>
      </DocSection>
      <DocSection id="glosario" title="Glosario">
        <ul>
          <li><strong>Sentinel-2:</strong> satélites del programa europeo Copernicus que fotografían la Tierra en 13 bandas, con píxeles de 10 a 60 m.</li>
          <li><strong>NDVI:</strong> índice de vegetación; valores altos indican vegetación verde y densa.</li>
          <li><strong>NBR:</strong> índice normalizado de quema; sensible a la estructura del bosque y a las cicatrices de fuego.</li>
          <li><strong>Composición:</strong> imagen sintética que combina varias fechas para eliminar nubes.</li>
          <li><strong>Polígono:</strong> contorno georreferenciado del área donde se detectó el cambio.</li>
        </ul>
      </DocSection>
      <DocSection id="roles" title="Roles">
        <ul>
          <li><strong>Observador:</strong> consulta mapas, alertas e informes.</li>
          <li><strong>Analista:</strong> crea zonas, lanza análisis, confirma o descarta alertas y envía informes.</li>
          <li><strong>Administración:</strong> gestiona usuarios y consulta la auditoría.</li>
        </ul>
      </DocSection>
    </DocPage>
  );
}
