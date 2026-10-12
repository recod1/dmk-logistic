import { onMounted, onUnmounted, ref, type Ref } from "vue";

export function useLiveNow(intervalMs = 1000): Ref<number> {
  const nowMs = ref(Date.now());
  let timer: number | null = null;
  onMounted(() => {
    nowMs.value = Date.now();
    timer = window.setInterval(() => {
      nowMs.value = Date.now();
    }, intervalMs);
  });
  onUnmounted(() => {
    if (timer != null) {
      window.clearInterval(timer);
      timer = null;
    }
  });
  return nowMs;
}
