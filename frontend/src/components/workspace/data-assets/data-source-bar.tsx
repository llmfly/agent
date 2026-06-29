"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseIcon, Loader2, PlusIcon, XIcon } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/workspace/tooltip";
import {
  detachDataSource,
  listAttachedDataSources,
} from "@/core/datasource/api";
import type { AttachedDataSource } from "@/core/datasource/types";
import { useI18n } from "@/core/i18n/hooks";

import { DataSourceAttachDialog } from "./data-source-attach-dialog";

interface Props {
  conversationId: string;
}

export function DataSourceBar({ conversationId }: Props) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [detaching, setDetaching] = useState<string | null>(null);

  const { data: attachedList = [], isLoading } = useQuery({
    queryKey: ["attached-datasources", conversationId],
    queryFn: () => listAttachedDataSources(conversationId),
    enabled: !!conversationId,
  });

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

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({
      queryKey: ["attached-datasources", conversationId],
    });
  }, [queryClient, conversationId]);

  if (!conversationId) return null;

  return (
    <>
      <div className="flex items-center gap-2 border-b px-4 py-1.5">
        <span className="text-muted-foreground flex items-center gap-1 text-xs font-medium">
          <DatabaseIcon className="size-3" />
          {t.dataAssets.title}:
        </span>
        {isLoading ? (
          <Loader2 className="size-3 animate-spin text-muted-foreground" />
        ) : attachedList.length === 0 ? (
          <span className="text-muted-foreground text-xs italic">
            {t.dataAssets.noAttachedConversations}
          </span>
        ) : (
          <div className="flex flex-wrap items-center gap-1.5">
            {attachedList.map((attached) => (
              <Badge
                key={attached.id}
                variant="secondary"
                className="gap-1 pr-1 text-xs"
              >
                <DatabaseIcon className="size-2.5" />
                {attached.alias || attached.name || attached.datasource_id.slice(0, 8)}
                <button
                  className="text-muted-foreground hover:text-foreground ml-0.5 inline-flex cursor-pointer"
                  onClick={() => handleDetach(attached.datasource_id)}
                  disabled={detaching === attached.datasource_id}
                >
                  {detaching === attached.datasource_id ? (
                    <Loader2 className="size-2.5 animate-spin" />
                  ) : (
                    <XIcon className="size-2.5" />
                  )}
                </button>
              </Badge>
            ))}
          </div>
        )}
        <Tooltip content={t.dataAssets.attach}>
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground ml-auto h-6 px-1.5"
            onClick={() => setDialogOpen(true)}
          >
            <PlusIcon className="size-3" />
            <span className="text-xs">{t.dataAssets.attach}</span>
          </Button>
        </Tooltip>
      </div>
      <DataSourceAttachDialog
        conversationId={conversationId}
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) invalidate();
        }}
      />
    </>
  );
}
