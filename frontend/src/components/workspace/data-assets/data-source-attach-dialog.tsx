"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseIcon, Link2Icon, Loader2, Unlink2Icon } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  listDataSources,
  attachDataSource,
  detachDataSource,
  listAttachedDataSources,
  updateAttach,
} from "@/core/datasource/api";
import type { AttachedDataSource, DataSource } from "@/core/datasource/types";
import { useI18n } from "@/core/i18n/hooks";

interface Props {
  conversationId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DataSourceAttachDialog({
  conversationId,
  open,
  onOpenChange,
}: Props) {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const { data: allDataSources = [], isLoading: loadingSources } = useQuery({
    queryKey: ["data-sources"],
    queryFn: () => listDataSources(),
  });

  const { data: attachedList = [], isLoading: loadingAttached } = useQuery({
    queryKey: ["attached-datasources", conversationId],
    queryFn: () => listAttachedDataSources(conversationId),
    enabled: !!conversationId,
  });

  const [attaching, setAttaching] = useState<string | null>(null);
  const [detaching, setDetaching] = useState<string | null>(null);
  const [editingAlias, setEditingAlias] = useState<{
    datasourceId: string;
    alias: string;
  } | null>(null);

  const attachedIds = new Set(attachedList.map((a) => a.datasource_id));
  const attachedMap = new Map<string, AttachedDataSource>(
    attachedList.map((a) => [a.datasource_id, a]),
  );

  const handleAttach = useCallback(
    async (datasourceId: string) => {
      setAttaching(datasourceId);
      try {
        await attachDataSource(conversationId, { datasource_id: datasourceId });
        toast.success("Data source attached");
        queryClient.invalidateQueries({
          queryKey: ["attached-datasources", conversationId],
        });
      } catch {
        toast.error("Failed to attach");
      } finally {
        setAttaching(null);
      }
    },
    [conversationId, queryClient],
  );

  const handleDetach = useCallback(
    async (datasourceId: string) => {
      setDetaching(datasourceId);
      try {
        await detachDataSource(conversationId, datasourceId);
        toast.success("Data source detached");
        queryClient.invalidateQueries({
          queryKey: ["attached-datasources", conversationId],
        });
      } catch {
        toast.error("Failed to detach");
      } finally {
        setDetaching(null);
      }
    },
    [conversationId, queryClient],
  );

  const handleUpdateAlias = useCallback(
    async (datasourceId: string) => {
      if (!editingAlias) return;
      try {
        await updateAttach(conversationId, datasourceId, {
          alias: editingAlias.alias,
        });
        toast.success("Alias updated");
        setEditingAlias(null);
        queryClient.invalidateQueries({
          queryKey: ["attached-datasources", conversationId],
        });
      } catch {
        toast.error("Failed to update alias");
      }
    },
    [conversationId, editingAlias, queryClient],
  );

  const isLoading = loadingSources || loadingAttached;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <DatabaseIcon className="size-5" />
            {t.dataAssets.attach} Data Sources
          </DialogTitle>
          <DialogDescription>
            Attach data sources to this conversation. The agent will have
            access to attached data sources.
          </DialogDescription>
        </DialogHeader>

        <Separator />

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : allDataSources.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            {t.dataAssets.emptyDescription}
          </div>
        ) : (
          <ScrollArea className="max-h-96">
            <div className="space-y-2 pr-2">
              {allDataSources.map((ds) => {
                const attached = attachedIds.has(ds.id);
                const attachedInfo = attachedMap.get(ds.id);
                const isEditingThis = editingAlias?.datasourceId === ds.id;

                return (
                  <div
                    key={ds.id}
                    className={`flex items-center justify-between rounded-lg border p-3 transition-colors ${
                      attached ? "bg-muted/50" : ""
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <DatabaseIcon
                          className={`size-4 ${attached ? "text-primary" : "text-muted-foreground"}`}
                        />
                        <span className="text-sm font-medium truncate">
                          {ds.name}
                        </span>
                        {attached && (
                          <Badge variant="outline" className="text-xs">
                            {t.dataAssets.attach}ed
                          </Badge>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant="secondary" className="text-[10px]">
                          {t.dataAssets.types[ds.type] || ds.type}
                        </Badge>
                        {attachedInfo?.alias && (
                          <span>
                            {t.dataAssets.alias}: {attachedInfo.alias}
                          </span>
                        )}
                      </div>
                      {attached && isEditingThis ? (
                        <div className="mt-2 flex items-center gap-2">
                          <Input
                            size={20}
                            placeholder={t.dataAssets.aliasPlaceholder}
                            value={editingAlias.alias}
                            onChange={(e) =>
                              setEditingAlias((prev) =>
                                prev
                                  ? { ...prev, alias: e.target.value }
                                  : null,
                              )
                            }
                            className="h-7 text-xs"
                          />
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-xs"
                            onClick={() => handleUpdateAlias(ds.id)}
                          >
                            {t.common.save}
                          </Button>
                        </div>
                      ) : null}
                    </div>
                    <div className="ml-3 flex items-center gap-1 shrink-0">
                      {attached ? (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-xs"
                            onClick={() =>
                              setEditingAlias({
                                datasourceId: ds.id,
                                alias: attachedInfo?.alias || "",
                              })
                            }
                          >
                            {t.dataAssets.alias}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-xs text-destructive"
                            onClick={() => handleDetach(ds.id)}
                            disabled={detaching === ds.id}
                          >
                            {detaching === ds.id ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <Unlink2Icon className="size-3" />
                            )}
                            {t.dataAssets.detach}
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => handleAttach(ds.id)}
                          disabled={attaching === ds.id}
                        >
                          {attaching === ds.id ? (
                            <Loader2 className="size-3 animate-spin" />
                          ) : (
                            <Link2Icon className="size-3" />
                          )}
                          {t.dataAssets.attach}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}

        <div className="flex justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t.common.close}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
