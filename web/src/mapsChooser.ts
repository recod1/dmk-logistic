import { computed, ref } from "vue";

export type MapsAppId = "apple" | "google" | "yandex" | "gis" | "geo";

export interface MapsAppLink {
  id: MapsAppId;
  label: string;
  href: string;
}

export type MapsChooserTarget =
  | { kind: "address"; address: string }
  | { kind: "coords"; lat: number; lng: number };

export const mapsChooserTarget = ref<MapsChooserTarget | null>(null);

export const mapsChooserAddress = computed(() => {
  const target = mapsChooserTarget.value;
  if (!target) {
    return null;
  }
  if (target.kind === "address") {
    return target.address;
  }
  return `${target.lat.toFixed(6)}, ${target.lng.toFixed(6)}`;
});

export function openMapsChooser(address: string): void {
  const trimmed = (address || "").trim();
  if (!trimmed) {
    return;
  }
  mapsChooserTarget.value = { kind: "address", address: trimmed };
}

export function openMapsChooserCoords(lat: number, lng: number): void {
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return;
  }
  mapsChooserTarget.value = { kind: "coords", lat, lng };
}

export function closeMapsChooser(): void {
  mapsChooserTarget.value = null;
}

export function mapsChooserApps(address: string): MapsAppLink[] {
  const q = encodeURIComponent(address.trim());
  return [
    { id: "apple", label: "Apple Карты", href: `https://maps.apple.com/?q=${q}` },
    { id: "google", label: "Google Maps", href: `https://www.google.com/maps/search/?api=1&query=${q}` },
    { id: "yandex", label: "Яндекс Карты", href: `https://yandex.ru/maps/?text=${q}` },
    { id: "gis", label: "2ГИС", href: `https://2gis.ru/search/${q}` },
    { id: "geo", label: "Другое приложение", href: `geo:0,0?q=${q}` }
  ];
}

export function mapsChooserAppsForTarget(target: MapsChooserTarget): MapsAppLink[] {
  if (target.kind === "address") {
    return mapsChooserApps(target.address);
  }
  const { lat, lng } = target;
  const q = encodeURIComponent(`${lat},${lng}`);
  return [
    { id: "apple", label: "Apple Карты", href: `https://maps.apple.com/?ll=${lat},${lng}&q=${q}` },
    { id: "google", label: "Google Maps", href: `https://www.google.com/maps/search/?api=1&query=${lat},${lng}` },
    { id: "yandex", label: "Яндекс Карты", href: `https://yandex.ru/maps/?pt=${lng},${lat}&z=16` },
    { id: "gis", label: "2ГИС", href: `https://2gis.ru/geo/${lng},${lat}` },
    { id: "geo", label: "Другое приложение", href: `geo:${lat},${lng}?q=${lat},${lng}` }
  ];
}
