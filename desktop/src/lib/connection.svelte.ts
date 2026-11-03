/**
 * Connection to the local engine: obtains port and token from the Tauri shell
 * (or, in browser development, from VITE_ENGINE_PORT / VITE_ENGINE_TOKEN),
 * creates the typed API client and keeps the event stream open, replaying
 * missed events after a reconnect.
 */
import { createApi, type Api } from "./api/client";
import { engineInfo, type EngineInfo } from "./engine";

export interface EngineEvent {
  seq: number;
  type: string;
  [key: string]: unknown;
}

type Listener = (event: EngineEvent) => void;

export const connection = $state<{
  status: "starting" | "ready" | "offline";
  info: EngineInfo | null;
  api: Api | null;
  demo: boolean;
  error: string;
}>({ status: "starting", info: null, api: null, demo: false, error: "" });

// Plain callbacks, not UI state: no reactivity needed.
// eslint-disable-next-line svelte/prefer-svelte-reactivity
const listeners = new Set<Listener>();
let lastSeq: number | null = null;
let socket: WebSocket | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function resolveInfo(): Promise<EngineInfo> {
  if (isTauri()) return engineInfo();
  const port = Number(import.meta.env.VITE_ENGINE_PORT);
  const token = String(import.meta.env.VITE_ENGINE_TOKEN ?? "");
  if (!port || !token) {
    throw new Error(
      "Outside the desktop app, set VITE_ENGINE_PORT and VITE_ENGINE_TOKEN.",
    );
  }
  return { port, token, pid: 0, version: "dev" };
}

export function onEvent(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function openEvents(info: EngineInfo): void {
  socket?.close();
  socket = new WebSocket(`ws://127.0.0.1:${info.port}/events`);
  socket.addEventListener("open", () => {
    socket?.send(JSON.stringify({ token: info.token, since: lastSeq }));
  });
  socket.addEventListener("message", (message) => {
    const event = JSON.parse(message.data) as EngineEvent;
    if (event.seq > 0) lastSeq = event.seq;
    if (event.type === "hello" || event.type === "heartbeat") return;
    listeners.forEach((listener) => listener(event));
  });
  socket.addEventListener("close", () => {
    connection.status = "offline";
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = setTimeout(() => void connect(), 2000);
  });
}

export async function connect(): Promise<void> {
  try {
    const info = connection.info ?? (await resolveInfo());
    const api = createApi(info);
    const { data, error } = await api.GET("/system");
    if (error || !data) throw new Error("engine did not answer");
    connection.info = info;
    connection.api = api;
    connection.demo = data.demo;
    connection.status = "ready";
    connection.error = "";
    openEvents(info);
  } catch (error) {
    connection.status = "offline";
    connection.error = String(error);
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = setTimeout(() => void connect(), 3000);
  }
}
