export type DataSourceType =
  | "mysql"
  | "postgresql"
  | "elasticsearch"
  | "pdf"
  | "docx"
  | "txt"
  | "xlsx"
  | "csv";

export type DataSourceStatus = "ready" | "error" | "testing";

export interface DataSource {
  id: string;
  user_id: string;
  name: string;
  description: string;
  type: DataSourceType;
  status: DataSourceStatus;
  icon: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  deleted: boolean;
}

export interface DataSourceCreateRequest {
  name: string;
  description?: string;
  type: DataSourceType;
  config: Record<string, unknown>;
}

export interface DataSourceUpdateRequest {
  name?: string;
  description?: string;
  config?: Record<string, unknown>;
}

export interface DataSourceListResponse {
  datasources: DataSource[];
  total: number;
}

export interface DataSourceTestRequest {
  type: DataSourceType;
  config: Record<string, unknown>;
}

export interface DataSourceTestResponse {
  success: boolean;
  message?: string;
}

export interface AttachDataSourceRequest {
  datasource_id: string;
  alias?: string;
}

export interface UpdateAttachRequest {
  alias?: string;
}

export interface AttachedDataSource {
  id: string;
  conversation_id: string;
  datasource_id: string;
  alias: string | null;
  mount_path: string | null;
  created_at: string;
  // Joined datasource info (flat fields from backend)
  name: string;
  type: string;
  status: string;
  icon: string;
  datasource?: DataSource;
}

export interface AttachedDataSourceListResponse {
  datasources: AttachedDataSource[];
}
