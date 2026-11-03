import createClient, { type Middleware } from "openapi-fetch";
import { baseUrl, type EngineInfo } from "$lib/engine";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type Api = ReturnType<typeof createApi>;

/** Typed client for the local engine API, generated from its OpenAPI schema. */
export function createApi(info: EngineInfo) {
  const auth: Middleware = {
    onRequest({ request }) {
      request.headers.set("Authorization", `Bearer ${info.token}`);
      return request;
    },
  };
  const client = createClient<paths>({ baseUrl: baseUrl(info) });
  client.use(auth);
  return client;
}

/** Error body returned by the engine for expected failures. */
export function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }
  return String(error);
}
