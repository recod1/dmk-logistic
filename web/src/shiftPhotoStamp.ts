export async function stampShiftPhoto(file: Blob, label: string, plate?: string): Promise<{ blob: Blob; issues: string[] }> {
  let src: ImageBitmap | HTMLImageElement | null = null;
  let srcUrl = "";
  try {
    try {
      src = await createImageBitmap(file);
    } catch {
      srcUrl = URL.createObjectURL(file);
      src = await new Promise<HTMLImageElement>((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error("не удалось прочитать фото"));
        img.src = srcUrl;
      });
    }
    const issues = qualityIssues(src);
    const max = 1600;
    const k = Math.min(1, max / Math.max(src.width, src.height));
    const w = Math.round(src.width * k);
    const h = Math.round(src.height * k);
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("нехватка памяти");
    ctx.drawImage(src, 0, 0, w, h);
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const stamp = `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()} ${pad(now.getHours())}:${pad(now.getMinutes())}   ${label}${plate ? `   ${plate.toUpperCase()}` : ""}`;
    const fs = Math.max(16, Math.round(w / 42));
    const bar = Math.round(fs * 2.2);
    ctx.fillStyle = "rgba(0,0,0,.6)";
    ctx.fillRect(0, h - bar, w, bar);
    ctx.fillStyle = "#fff";
    ctx.font = `600 ${fs}px system-ui,sans-serif`;
    ctx.textBaseline = "middle";
    ctx.fillText(stamp, Math.round(fs * 0.7), h - bar / 2);
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((item) => (item ? resolve(item) : reject(new Error("нехватка памяти при сжатии"))), "image/jpeg", 0.8);
    });
    canvas.width = canvas.height = 0;
    return { blob, issues };
  } finally {
    if (src && "close" in src && typeof src.close === "function") src.close();
    if (srcUrl) URL.revokeObjectURL(srcUrl);
  }
}

function qualityIssues(src: { width: number; height: number } & CanvasImageSource): string[] {
  const W = 320;
  const H = Math.max(3, Math.round((src as { height: number }).height * W / Math.max(1, (src as { width: number }).width)));
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const x = c.getContext("2d", { willReadFrequently: true });
  if (!x) return [];
  x.drawImage(src, 0, 0, W, H);
  const data = x.getImageData(0, 0, W, H).data;
  const n = W * H;
  let sum = 0;
  let hi = 0;
  const g = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    const v = 0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2];
    g[i] = v;
    sum += v;
    if (v > 245) hi += 1;
  }
  const mean = sum / n;
  let sq = 0;
  for (let i = 0; i < n; i += 1) {
    const t = g[i] - mean;
    sq += t * t;
  }
  const std = Math.sqrt(sq / n);
  c.width = c.height = 0;
  const out: string[] = [];
  const hour = new Date().getHours();
  const night = hour < 6 || hour >= 21;
  if (night) {
    if (mean < 8) out.push("Почти чёрный кадр: закрыт объектив или совсем нет света");
  } else if (mean < 55) {
    out.push("Слишком тёмное: подойдите к свету или включите вспышку");
  }
  if (hi / n > 0.35 && mean > 190) out.push("Пересвечено: блики или солнце в объективе, смените ракурс");
  if (mean >= 8 && (!night && std < 12)) out.push("Смазано или не в фокусе: держите телефон неподвижно");
  return out;
}
