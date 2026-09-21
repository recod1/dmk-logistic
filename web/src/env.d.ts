/// <reference types="vite/client" />

interface SyncEvent extends ExtendableEvent {
  readonly tag: string;
}

interface PeriodicSyncEvent extends ExtendableEvent {
  readonly tag: string;
}

