"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Database,
  Download,
  Loader2,
  PanelRightClose,
  Plus,
  Trash2,
} from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import {
  detachDataSource,
  listAttachedDataSources,
} from "@/core/datasource/api";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

import { DataSourceAttachDialog } from "./data-source-attach-dialog";

interface Props {
  conversationId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DataSourcePanel({ conversationId, open, onOpenChange }: Props) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [detaching, setDetaching] = useState<string | null>(null);

  const { data: attachedList = [], isLoading } = useQuery({
    queryKey: ["attached-datasources", conversationId],
    queryFn: () => listAttachedDataSources(conversationId),
    enabled: !!conversationId && open,
  });

  const handleDetach = useCallback(
    async (datasourceId: string) => {
      setDetaching(datasourceId);
      try {
        await detachDataSource(conversationId, datasourceId);
        toast.success("Data source detached");
        void queryClient.invalidateQueries({
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

  const handleDialogClose = useCallback(
    (open: boolean) => {
      setDialogOpen(open);
      if (!open) {
        void queryClient.invalidateQueries({
          queryKey: ["attached-datasources", conversationId],
        });
      }
    },
    [conversationId, queryClient],
  );

  if (!conversationId) return null;

  return (
    <>
      <div className="bg-sidebar text-sidebar-foreground flex size-full flex-col border-l border-sidebar-border">
        {/* Header — title + action icons (matches left sidebar header padding) */}
        <div className="flex items-center justify-between px-4 pt-3 pb-1">
          <span className="text-sm font-medium">
            {t.dataAssets.title}
          </span>
          <div className="flex items-center gap-1">
            <button className="text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground flex items-center justify-center rounded-md p-1.5 transition-colors">
              <Download className="size-4" />
            </button>
            <button
              className="text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground flex items-center justify-center rounded-md p-1.5 transition-colors"
              onClick={() => onOpenChange(false)}
            >
              <PanelRightClose className="size-4" />
            </button>
          </div>
        </div>

        {/* "+ 关联" button — styled like sidebar menu item */}
        <div className="px-2 pt-1 pb-0">
          <button
            className={cn(
              "flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-left text-sm outline-hidden",
              "transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              "[&>svg]:size-4 [&>svg]:shrink-0",
            )}
            onClick={() => setDialogOpen(true)}
          >
            <Plus className="size-4" />
            <span className="truncate">{t.dataAssets.attach}</span>
          </button>
        </div>

        {/* Section title */}
        <div className="text-sidebar-foreground/70 flex h-8 shrink-0 items-center rounded-md px-4 text-xs font-medium">
          {t.dataAssets.title}
        </div>

        {/* Content area — asset list */}
        <div className="flex-1 overflow-auto px-2 pb-2">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="text-sidebar-foreground/50 size-5 animate-spin" />
            </div>
          ) : attachedList.length === 0 ? (
            <div className="flex items-center gap-2 px-2 py-2">
              <Database className="text-sidebar-foreground/50 size-4 shrink-0" />
              <span className="text-sidebar-foreground/70 text-sm">
                {t.dataAssets.noAttachedConversations}
              </span>
            </div>
          ) : (
            <ul className="flex w-full min-w-0 flex-col gap-1">
              {attachedList.map((attached) => (
                <li key={attached.id} className="group/menu-item relative">
                  <div
                    className={cn(
                      "group/ds-item flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-left text-sm outline-hidden",
                      "transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                      "[&>svg]:size-4 [&>svg]:shrink-0",
                    )}
                  >
                    <Database className="text-sidebar-foreground/50 size-4 shrink-0" />
                    <div className="min-w-0 flex-1 text-left">
                      <span className="text-sidebar-foreground/80 block truncate text-sm transition-colors">
                        {attached.alias ?? attached.name ?? attached.datasource_id.slice(0, 8)}
                      </span>
                      <span className="text-sidebar-foreground/50 block text-[11px]">
                        {t.dataAssets.types[attached.type as keyof typeof t.dataAssets.types] || attached.type || "—"}
                      </span>
                    </div>
                    <button
                      className="text-sidebar-foreground/50 hover:text-sidebar-accent-foreground hidden items-center justify-center rounded p-1 transition-colors group-hover/ds-item:flex"
                      onClick={() => handleDetach(attached.datasource_id)}
                      disabled={detaching === attached.datasource_id}
                    >
                      {detaching === attached.datasource_id ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="size-3.5" />
                      )}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <DataSourceAttachDialog
        conversationId={conversationId}
        open={dialogOpen}
        onOpenChange={handleDialogClose}
      />
    </>
  );
}
