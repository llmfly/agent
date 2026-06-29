import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  AttachDataSourceRequest,
  AttachedDataSource,
  AttachedDataSourceListResponse,
  DataSource,
  DataSourceCreateRequest,
  DataSourceListResponse,
  DataSourceTestRequest,
  DataSourceTestResponse,
  DataSourceUpdateRequest,
  DataSourceUploadResponse,
  UpdateAttachRequest,
} from "./types";

const BASE = `${getBackendBaseURL()}/api/v1/workspace`;

// ---- Data Sources CRUD ----

export async function listDataSources(params?: {
  type?: string;
  search?: string;
}): Promise<DataSource[]> {
  const searchParams = new URLSearchParams();
  if (params?.type) searchParams.set("type", params.type);
  if (params?.search) searchParams.set("search", params.search);
  const qs = searchParams.toString();
  const url = `${BASE}/data-sources${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  const json = (await res.json()) as DataSourceListResponse;
  return json.datasources;
}

export async function getDataSource(id: string): Promise<DataSource> {
  const res = await fetch(`${BASE}/data-sources/${id}`);
  return res.json() as Promise<DataSource>;
}

export async function createDataSource(
  req: DataSourceCreateRequest,
): Promise<DataSource> {
  const res = await fetch(`${BASE}/data-sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return res.json() as Promise<DataSource>;
}

export async function updateDataSource(
  id: string,
  req: DataSourceUpdateRequest,
): Promise<DataSource> {
  const res = await fetch(`${BASE}/data-sources/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return res.json() as Promise<DataSource>;
}

export async function deleteDataSource(id: string): Promise<void> {
  await fetch(`${BASE}/data-sources/${id}`, { method: "DELETE" });
}

export async function testConnection(
  req: DataSourceTestRequest,
): Promise<DataSourceTestResponse> {
  const res = await fetch(`${BASE}/data-sources/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return res.json() as Promise<DataSourceTestResponse>;
}

// ---- File Upload for Data Sources ----

export async function uploadDataSourceFile(
  file: File,
): Promise<DataSourceUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/data-sources/upload`, {
    method: "POST",
    body: formData,
  });
  return res.json() as Promise<DataSourceUploadResponse>;
}

// ---- Attach / Detach ----

export async function attachDataSource(
  conversationId: string,
  req: AttachDataSourceRequest,
): Promise<AttachedDataSource> {
  const res = await fetch(
    `${BASE}/conversations/${conversationId}/datasources`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
  return res.json() as Promise<AttachedDataSource>;
}

export async function listAttachedDataSources(
  conversationId: string,
): Promise<AttachedDataSource[]> {
  const res = await fetch(
    `${BASE}/conversations/${conversationId}/datasources`,
  );
  const json = (await res.json()) as AttachedDataSourceListResponse;
  return json.datasources;
}

export async function detachDataSource(
  conversationId: string,
  datasourceId: string,
): Promise<void> {
  await fetch(
    `${BASE}/conversations/${conversationId}/datasources/${datasourceId}`,
    { method: "DELETE" },
  );
}

export async function updateAttach(
  conversationId: string,
  datasourceId: string,
  req: UpdateAttachRequest,
): Promise<AttachedDataSource> {
  const res = await fetch(
    `${BASE}/conversations/${conversationId}/datasources/${datasourceId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
  return res.json() as Promise<AttachedDataSource>;
}
