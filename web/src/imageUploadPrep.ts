/** Ужимает снимки перед отправкой: меньше тело запроса, ниже шанс 413 на прокси. */

const MAX_EDGE_PX = 2560;
const JPEG_QUALITY = 0.82;
const SKIP_CANVAS_MAX_BYTES = 2.5 * 1024 * 1024;

async function imageToScaledJpegBlob(bitmap: ImageBitmap, maxEdge: number, quality: number): Promise<Blob> {
  let { width, height } = bitmap;
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  const w = Math.max(1, Math.round(width * scale));
  const h = Math.max(1, Math.round(height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Canvas недоступен");
  }
  ctx.drawImage(bitmap, 0, 0, w, h);
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((b) => resolve(b), "image/jpeg", quality);
  });
  if (!blob) {
    throw new Error("Не удалось сжать изображение");
  }
  return blob;
}

export async function prepareDocumentImageBlobs(blobs: Blob[]): Promise<Blob[]> {
  const files = blobs.map(
    (blob, i) => new File([blob], `doc-${i}.jpg`, { type: blob.type || "image/jpeg" })
  );
  return prepareDocumentImageFiles(files);
}

export async function prepareDocumentImageFiles(files: File[]): Promise<Blob[]> {
  const out: Blob[] = [];
  for (const file of files) {
    if (!file.type.startsWith("image/")) {
      out.push(file);
      continue;
    }
    let bitmap: ImageBitmap | null = null;
    try {
      bitmap = await createImageBitmap(file);
    } catch {
      out.push(file);
      continue;
    }
    try {
      const maxDim = Math.max(bitmap.width, bitmap.height);
      const needsWork = maxDim > MAX_EDGE_PX || file.size > SKIP_CANVAS_MAX_BYTES || file.type !== "image/jpeg";
      if (!needsWork) {
        out.push(file);
        continue;
      }
      out.push(await imageToScaledJpegBlob(bitmap, MAX_EDGE_PX, JPEG_QUALITY));
    } catch {
      out.push(file);
    } finally {
      bitmap.close();
    }
  }
  return out;
}
