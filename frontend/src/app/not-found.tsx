import { ButtonLink } from "@/components/ui/Button";
import { OrbitIllustration } from "@/components/ui/Feedback";

export default function NotFound() {
  return (
    <main id="contenido" className="grid min-h-[100svh] place-items-center px-5 text-center">
      <div className="flex flex-col items-center gap-5">
        <OrbitIllustration className="size-40" />
        <p className="eyebrow">Error 404 · fuera de órbita</p>
        <h1 className="font-display display-tight text-5xl text-ink">Esta página no está en el mapa.</h1>
        <p className="max-w-md text-ink-2">Puede que el enlace esté incompleto o que el recurso haya sido eliminado.</p>
        <ButtonLink href="/">Volver al inicio</ButtonLink>
      </div>
    </main>
  );
}
