/**
 * Sombreado de la Tierra: NASA Blue Marble (día) / Black Marble (noche) ajustados hacia la
 * paleta de Forest Sentinel. Esto es una representación *artística* del planeta — nunca se
 * presenta como dato científico (así está indicado en la UI).
 */
export const earthVertex = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  void main() {
    vUv = uv;
    vec4 world = modelMatrix * vec4(position, 1.0);
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - world.xyz);
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

export const earthFragment = /* glsl */ `
  uniform sampler2D uDay;
  uniform sampler2D uNight;
  uniform vec3 uSun;
  uniform float uTime;
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vViewDir;

  void main() {
    vec3 day = texture2D(uDay, vUv).rgb;
    float lum = dot(day, vec3(0.299, 0.587, 0.114));
    // Grade: deepen oceans, push vegetation toward the brand greens.
    float isLand = smoothstep(0.08, 0.22, day.g - day.b * 0.6 + lum * 0.4);
    vec3 ocean = mix(vec3(0.02, 0.05, 0.05), vec3(0.06, 0.14, 0.13), lum * 2.0);
    vec3 land = mix(vec3(lum) * vec3(0.62, 0.78, 0.62), day * vec3(0.85, 1.05, 0.82), 0.6);
    vec3 graded = mix(ocean, land, isLand);

    vec3 night = texture2D(uNight, vUv).rgb;
    night = pow(night, vec3(1.6)) * vec3(1.0, 0.78, 0.48) * 2.2;

    float ndl = dot(normalize(vNormalW), normalize(uSun));
    float dayMix = smoothstep(-0.18, 0.32, ndl);
    vec3 color = mix(night + graded * 0.05, graded * (0.35 + 0.75 * max(ndl, 0.0)), dayMix);

    // Thin terminator glow and atmospheric rim.
    float terminator = smoothstep(0.18, 0.0, abs(ndl)) * 0.12;
    color += vec3(0.57, 0.78, 0.48) * terminator;
    float fresnel = pow(1.0 - max(dot(vViewDir, normalize(vNormalW)), 0.0), 3.0);
    color += vec3(0.45, 0.78, 0.55) * fresnel * 0.55;

    gl_FragColor = vec4(color, 1.0);
    #include <colorspace_fragment>
  }
`;

export const atmosphereVertex = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - world.xyz);
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

export const atmosphereFragment = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  void main() {
    float rim = 1.0 - abs(dot(vViewDir, normalize(vNormalW)));
    float intensity = pow(rim, 4.0) * 1.4;
    gl_FragColor = vec4(vec3(0.49, 0.80, 0.55) * intensity, intensity);
  }
`;

export const dustVertex = /* glsl */ `
  attribute float aScale;
  uniform float uTime;
  uniform float uPixelRatio;
  varying float vAlpha;
  void main() {
    vec3 p = position;
    p.y += sin(uTime * 0.15 + position.x * 3.0) * 0.04;
    p.x += cos(uTime * 0.11 + position.z * 2.0) * 0.04;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = aScale * uPixelRatio * (18.0 / -mv.z);
    vAlpha = smoothstep(9.0, 2.0, -mv.z) * 0.55;
  }
`;

export const dustFragment = /* glsl */ `
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.0, d) * vAlpha;
    gl_FragColor = vec4(0.82, 0.90, 0.72, a);
  }
`;
