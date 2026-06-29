"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftIcon,
  DatabaseIcon,
  EditIcon,
  Loader2,
  SaveIcon,
  Trash2Icon,
  WifiIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getDataSource,
  testConnection,
  updateDataSource,
  deleteDataSource,
} from "@/core/datasource/api";
import type { DataSource } from "@/core/datasource/types";
import { useI18n } from "@/core/i18n/hooks";

type EditableFields = {
  name: string;
  description: string;
  config: Record<string, unknown>;
};

export default function DataSourceDetailPage() {
  const { t } = useI18n();
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id as string;

  const { data: ds, isLoading } = useQuery<DataSource>({
    queryKey: ["data-source", id],
    queryFn: () => getDataSource(id),
  });

  const [editing, setEditing] = useState(false);
  const [editFields, setEditFields] = useState<EditableFields>({
    name: "",
    description: "",
    config: {},
  });
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const startEditing = useCallback(() => {
    if (!ds) return;
    setEditFields({
      name: ds.name,
      description: ds.description,
      config: { ...ds.config },
    });
    setEditing(true);
  }, [ds]);

  const handleTest = useCallback(async () => {
    if (!ds) return;
    setTesting(true);
    try {
      const result = await testConnection({
        type: ds.type,
        config: editing ? editFields.config : ds.config,
      });
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
  }, [ds, editing, editFields, t]);

  const handleSave = useCallback(async () => {
    if (!ds) return;
    setSaving(true);
    try {
      await updateDataSource(ds.id, {
        name: editFields.name.trim(),
        description: editFields.description.trim(),
        config: editFields.config,
      });
      toast.success("Data source updated");
      queryClient.invalidateQueries({ queryKey: ["data-source", id] });
      queryClient.invalidateQueries({ queryKey: ["data-sources"] });
      setEditing(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Update failed: ${msg}`);
    } finally {
      setSaving(false);
    }
  }, [ds, editFields, queryClient, id]);

  const handleDelete = useCallback(async () => {
    if (!ds) return;
    if (!confirm(t.dataAssets.deleteConfirm)) return;
    setDeleting(true);
    try {
      await deleteDataSource(ds.id);
      toast.success(t.dataAssets.deleteSuccess);
      queryClient.invalidateQueries({ queryKey: ["data-sources"] });
      router.push("/workspace/data-assets");
    } catch {
      toast.error("Delete failed");
      setDeleting(false);
    }
  }, [ds, t, queryClient, router]);

  const updateConfig = useCallback((key: string, value: string) => {
    setEditFields((prev) => ({
      ...prev,
      config: { ...prev.config, [key]: value },
    }));
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-full flex-col">
        <div className="border-b px-6 py-4">
          <Skeleton className="h-6 w-48" />
        </div>
        <div className="flex-1 space-y-4 p-6">
          <Skeleton className="h-32 w-full max-w-2xl" />
          <Skeleton className="h-48 w-full max-w-2xl" />
        </div>
      </div>
    );
  }

  if (!ds) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <DatabaseIcon className="text-muted-foreground size-12" />
        <p className="text-muted-foreground">Data source not found</p>
        <Button asChild variant="outline">
          <Link href="/workspace/data-assets">Back to Data Assets</Link>
        </Button>
      </div>
    );
  }

  const configFields = Object.entries(ds.config ?? {}).filter(
    ([key]) => key !== "ssl",
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/workspace/data-assets">
              <ArrowLeftIcon className="size-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              {editing ? (
                <Input
                  className="inline-flex h-8 w-64"
                  value={editFields.name}
                  onChange={(e) =>
                    setEditFields((p) => ({ ...p, name: e.target.value }))
                  }
                />
              ) : (
                <>{ds.name}</>
              )}
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={testing}
          >
            {testing ? (
              <Loader2 className="mr-2 size-3 animate-spin" />
            ) : (
              <WifiIcon className="mr-2 size-3" />
            )}
            {t.dataAssets.testConnection}
          </Button>
          {editing ? (
            <>
              <Button size="sm" onClick={handleSave} disabled={saving}>
                {saving ? (
                  <Loader2 className="mr-2 size-3 animate-spin" />
                ) : (
                  <SaveIcon className="mr-2 size-3" />
                )}
                {t.common.save}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditing(false)}
              >
                {t.common.cancel}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={startEditing}
              >
                <EditIcon className="mr-2 size-3" />
                {t.common.edit}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting ? (
                  <Loader2 className="mr-2 size-3 animate-spin" />
                ) : (
                  <Trash2Icon className="mr-2 size-3" />
                )}
                {t.common.delete}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="mx-auto max-w-2xl space-y-6">
          {/* Info Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {t.dataAssets.basicInfo}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-muted-foreground text-xs">
                    {t.dataAssets.type}
                  </span>
                  <p className="mt-1">{t.dataAssets.types[ds.type] || ds.type}</p>
                </div>
                <div>
                  <span className="text-muted-foreground text-xs">Status</span>
                  <p className="mt-1">
                    <Badge
                      variant={ds.status === "ready" ? "default" : "secondary"}
                    >
                      {t.dataAssets.status[ds.status]}
                    </Badge>
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground text-xs">
                    {t.dataAssets.name}
                  </span>
                  <p className="mt-1">{ds.name}</p>
                </div>
                <div>
                  <span className="text-muted-foreground text-xs">
                    {t.dataAssets.description}
                  </span>
                  <p className="mt-1">{ds.description || "-"}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Connection Config Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {t.dataAssets.connectionConfig}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {editing
                ? Object.entries(editFields.config).map(([key, value]) => (
                    <div key={key} className="space-y-2">
                      <span className="text-sm font-medium capitalize">
                        {key}
                      </span>
                      <Input
                        type={key === "password" ? "password" : "text"}
                        value={String(value ?? "")}
                        onChange={(e) => updateConfig(key, e.target.value)}
                      />
                    </div>
                  ))
                : configFields.map(([key, value]) => (
                    <div key={key}>
                      <span className="text-muted-foreground text-xs capitalize">
                        {key}
                      </span>
                      <p className="mt-1 font-mono text-sm">
                        {key === "password"
                          ? "********"
                          : String(value ?? "")}
                      </p>
                    </div>
                  ))}
            </CardContent>
          </Card>

          {/* Meta */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Metadata</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground text-xs">ID</span>
                  <p className="mt-1 font-mono">{ds.id}</p>
                </div>
                <div>
                  <span className="text-muted-foreground text-xs">
                    Created
                  </span>
                  <p className="mt-1">
                    {new Date(ds.created_at).toLocaleString()}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground text-xs">
                    Updated
                  </span>
                  <p className="mt-1">
                    {new Date(ds.updated_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
