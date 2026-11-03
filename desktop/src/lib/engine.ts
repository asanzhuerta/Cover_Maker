import { invoke } from "@tauri-apps/api/core";

/** How to reach the local engine (returned by the shell). */
export interface EngineInfo {
  port: number;
  token: string;
  pid: number;
  version: string;
}

export function baseUrl(info: EngineInfo): string {
  return `http://127.0.0.1:${info.port}`;
}

/** Ask the shell for the engine, starting it if needed. */
export function engineInfo(): Promise<EngineInfo> {
  return invoke<EngineInfo>("engine_info");
}

export async function health(
  info: EngineInfo,
): Promise<{ status: string; version: string }> {
  const response = await fetch(`${baseUrl(info)}/health`, {
    headers: { Authorization: `Bearer ${info.token}` },
  });
  if (!response.ok) throw new Error(`engine answered ${response.status}`);
  return response.json();
}

/** Open the event stream; the token is sent as the first message. */
export function connectEvents(
  info: EngineInfo,
  onEvent: (event: { seq: number; type: string }) => void,
): WebSocket {
  const socket = new WebSocket(`ws://127.0.0.1:${info.port}/events`);
  socket.addEventListener("open", () =>
    socket.send(JSON.stringify({ token: info.token })),
  );
  socket.addEventListener("message", (message) =>
    onEvent(JSON.parse(message.data)),
  );
  return socket;
}
