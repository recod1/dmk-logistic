import { registerSW } from "virtual:pwa-register";

type UpdateSW = (reloadPage?: boolean) => Promise<void>;

let updateSW: UpdateSW | null = null;

export function initAppUpdate(): void {
  updateSW = registerSW({ immediate: true });
}

export async function applyLatestAppVersion(): Promise<"reloading" | "current"> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    return "current";
  }
  try {
    const registration = await navigator.serviceWorker.getRegistration();
    if (registration) {
      await registration.update();
    }
    const latest = registration ?? (await navigator.serviceWorker.getRegistration());
    const waiting = latest?.waiting;
    const installing = latest?.installing;
    if (!waiting && !installing) {
      return "current";
    }
    waiting?.postMessage({ type: "SKIP_WAITING" });
    await new Promise<void>((resolve) => {
      const done = () => resolve();
      navigator.serviceWorker.addEventListener("controllerchange", done, { once: true });
      window.setTimeout(done, 1500);
    });
    if (updateSW) {
      await updateSW(true);
    } else {
      window.location.reload();
    }
    return "reloading";
  } catch {
    return "current";
  }
}
