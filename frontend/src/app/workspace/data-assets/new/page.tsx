"use client";

import {
  ArrowLeftIcon,
  CheckIcon,
  FileUpIcon,
  Loader2,
  Trash2,
  WifiIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { testConnection, uploadDataSourceFile } from "@/core/datasource/api";
import type { DataSourceType } from "@/core/datasource/types";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

import { useDataSources } from "../use-data-sources";

// ── File-type data sources that require file upload ──────────────────────
const FILE_DATA_SOURCE_TYPES = new Set<DataSourceType>([
  "pdf", "docx", "txt", "xlsx", "csv",
]);

const TYPE_CONFIG_FIELDS: Record<
  DataSourceType,
  { key: string; label: string; placeholder: string; type: string }[]
> = {
  mysql: [
    { key: "host", label: "Host", placeholder: "127.0.0.1", type: "text" },
    { key: "port", label: "Port", placeholder: "3306", type: "number" },
    { key: "user", label: "Username", placeholder: "root", type: "text" },
    {
      key: "password",
      label: "Password",
      placeholder: "********",
      type: "password",
    },
    {
      key: "database",
      label: "Database",
      placeholder: "my_database",
      type: "text",
    },
  ],
  postgresql: [
    { key: "host", label: "Host", placeholder: "127.0.0.1", type: "text" },
    { key: "port", label: "Port", placeholder: "5432", type: "number" },
    { key: "user", label: "Username", placeholder: "postgres", type: "text" },
    {
      key: "password",
      label: "Password",
      placeholder: "********",
      type: "password",
    },
    {
      key: "database",
      label: "Database",
      placeholder: "my_database",
      type: "text",
    },
  ],
  elasticsearch: [
    { key: "host", label: "Host", placeholder: "127.0.0.1", type: "text" },
    { key: "port", label: "Port", placeholder: "9200", type: "number" },
    {
      key: "username",
      label: "Username",
      placeholder: "elastic",
      type: "text",
    },
    {
      key: "password",
      label: "Password",
      placeholder: "********",
      type: "password",
    },
  ],
  pdf: [{ key: "description", label: "文件说明", placeholder: "可选，描述该 PDF 数据源的内容", type: "text" }],
  docx: [{ key: "description", label: "文件说明", placeholder: "可选，描述该 Word 数据源的内容", type: "text" }],
  txt: [{ key: "description", label: "文件说明", placeholder: "可选，描述该文本数据源的内容", type: "text" }],
  xlsx: [{ key: "description", label: "文件说明", placeholder: "可选，描述该 Excel 数据源的内容", type: "text" }],
  csv: [{ key: "description", label: "文件说明", placeholder: "可选，描述该 CSV 数据源的内容", type: "text" }],
};

function defaultConfig(type: DataSourceType): Record<string, unknown> {
  const config: Record<string, unknown> = {};
  for (const field of TYPE_CONFIG_FIELDS[type]) {
    if (field.key === "port") config[field.key] = parseInt(field.placeholder);
    else config[field.key] = "";
  }
  return config;
}

export default function NewDataSourcePage() {
  const { t } = useI18n();
  const router = useRouter();
  const { createMutate } = useDataSources();

  const [type, setType] = useState<DataSourceType>("mysql");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [config, setConfig] = useState<Record<string, unknown>>(
    defaultConfig("mysql"),
  );
  const [testing, setTesting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isFileType = FILE_DATA_SOURCE_TYPES.has(type);

  const updateConfig = useCallback((key: string, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleTypeChange = useCallback(
    (newType: DataSourceType) => {
      setType(newType);
      setConfig(defaultConfig(newType));
      setSelectedFile(null);
    },
    [],
  );

  const handleTest = useCallback(async () => {
    setTesting(true);
    try {
      const result = await testConnection({ type, config });
      if (result.success) {
        toast.success(t.dataAssets.testSuccess);
      } else {
        toast.error(
          t.dataAssets.testFailed.replace("{error}", result.message || ""),
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(t.dataAssets.testFailed.replace("{error}", msg));
    } finally {
      setTesting(false);
    }
  }, [type, config, t]);

  const handleSubmit = useCallback(async () => {
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }

    if (isFileType && !selectedFile) {
      toast.error("Please select a file to upload");
      return;
    }

    try {
      let finalConfig = { ...config };

      // Upload file first for file-type data sources
      if (isFileType && selectedFile) {
        setUploading(true);
        const uploadResult = await uploadDataSourceFile(selectedFile);
        finalConfig = uploadResult.config as Record<string, unknown>;
        setUploading(false);
      }

      const result = await createMutate.mutateAsync({
        name: name.trim(),
        description: description.trim(),
        type,
        config: finalConfig,
      });
      toast.success("Data source created!");
      router.push(`/workspace/data-assets/${result.id}`);
    } catch (err: unknown) {
      setUploading(false);
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Failed to create: ${msg}`);
    }
  }, [name, description, type, config, isFileType, selectedFile, createMutate, router]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-4 border-b px-6 py-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/workspace/data-assets">
            <ArrowLeftIcon className="size-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            {t.dataAssets.newDataSource}
          </h1>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {/* Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {t.dataAssets.basicInfo}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <span className="text-sm font-medium">{t.dataAssets.type}</span>
                <Select
                  value={type}
                  onValueChange={(v) =>
                    handleTypeChange(v as DataSourceType)
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mysql">
                      {t.dataAssets.types.mysql}
                    </SelectItem>
                    <SelectItem value="postgresql">
                      {t.dataAssets.types.postgresql}
                    </SelectItem>
                    <SelectItem value="elasticsearch">
                      {t.dataAssets.types.elasticsearch}
                    </SelectItem>
                    <SelectItem value="pdf">
                      {t.dataAssets.types.pdf}
                    </SelectItem>
                    <SelectItem value="docx">
                      {t.dataAssets.types.docx}
                    </SelectItem>
                    <SelectItem value="txt">
                      {t.dataAssets.types.txt}
                    </SelectItem>
                    <SelectItem value="xlsx">
                      {t.dataAssets.types.xlsx}
                    </SelectItem>
                    <SelectItem value="csv">
                      {t.dataAssets.types.csv}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <span className="text-sm font-medium">{t.dataAssets.name}</span>
                <Input
                  placeholder={t.dataAssets.namePlaceholder}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <span className="text-sm font-medium">{t.dataAssets.descriptionLabel}</span>
                <Textarea
                  placeholder={t.dataAssets.descriptionPlaceholder}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                />
              </div>
            </CardContent>
          </Card>

          {isFileType ? (
            /* ── File Upload Section (for pdf/docx/txt/xlsx/csv) ───── */
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  {t.dataAssets.fileUpload}
                </CardTitle>
                <CardDescription>
                  选择对应类型的文件上传，系统将自动解析文件内容。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={{
                    pdf: ".pdf",
                    docx: ".docx,.doc",
                    txt: ".txt",
                    xlsx: ".xlsx,.xls",
                    csv: ".csv",
                  }[type] || undefined}
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) setSelectedFile(file);
                  }}
                />
                {selectedFile ? (
                  <div className="border-2 border-dashed rounded-lg p-6 text-center space-y-3">
                    <div className="text-sm font-medium text-foreground">
                      {selectedFile.name}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedFile(null);
                        if (fileInputRef.current) fileInputRef.current.value = "";
                      }}
                    >
                      <Trash2 className="mr-1 size-3" />
                      重新选择
                    </Button>
                  </div>
                ) : (
                  <div
                    className={cn(
                      "border-2 border-dashed rounded-lg p-10 text-center cursor-pointer",
                      "transition-colors hover:border-primary hover:bg-accent/30",
                    )}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <FileUpIcon className="mx-auto mb-3 size-10 text-muted-foreground" />
                    <div className="text-sm font-medium text-foreground">
                      点击或拖拽上传文件
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      支持 {
                        { pdf: "PDF (.pdf)", docx: "Word (.docx/.doc)", txt: "Text (.txt)", xlsx: "Excel (.xlsx/.xls)", csv: "CSV (.csv)" }[type]
                      } 格式（最大 50MB）
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            /* ── Connection Config Section (for SQL types) ─────────── */
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  {t.dataAssets.connectionConfig}
                </CardTitle>
                <CardDescription>
                  Configure the connection parameters for your {type} data source.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {TYPE_CONFIG_FIELDS[type].map((field) => (
                  <div key={field.key} className="space-y-2">
                    <span className="text-sm font-medium">{field.label}</span>
                    <Input
                      type={field.type}
                      placeholder={field.placeholder}
                      value={String(config[field.key] ?? "")}
                      onChange={(e) => updateConfig(field.key, e.target.value)}
                    />
                  </div>
                ))}
                <Button
                  variant="outline"
                  onClick={handleTest}
                  disabled={testing}
                >
                  {testing ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <WifiIcon className="mr-2 size-4" />
                  )}
                  {t.dataAssets.testConnection}
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3 pb-8">
            <Button
              size="lg"
              onClick={handleSubmit}
              disabled={createMutate.isPending || uploading}
            >
              {uploading || createMutate.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <CheckIcon className="mr-2 size-4" />
              )}
              {uploading ? "上传中..." : t.common.create}
            </Button>
            <Button variant="outline" size="lg" asChild>
              <Link href="/workspace/data-assets">{t.common.cancel}</Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
