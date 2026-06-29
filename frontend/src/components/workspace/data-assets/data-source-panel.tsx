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
      <div className="flex size-full flex-col bg-[#1A1A1C]">
        {/* Header — title + action icons */}
        <div className="flex items-center justify-between px-4">
          <span className="text-[#F5F5F7] text-base font-medium">
            {t.dataAssets.title}
          </span>
          <div className="flex items-center gap-1">
            {/* Export button */}
            <button className="flex items-center justify-center rounded-[6px] p-1.5 text-[#8A8A91] transition-colors hover:bg-[#27272A] hover:text-white">
              <Download className="size-4" />
            </button>
            {/* Collapse button */}
            <button
              className="flex items-center justify-center rounded-[6px] p-1.5 text-[#8A8A91] transition-colors hover:bg-[#27272A] hover:text-white"
              onClick={() => onOpenChange(false)}
            >
              <PanelRightClose className="size-4" />
            </button>
          </div>
        </div>

        {/* Divider */}
        <div className="mx-0 my-2 h-px bg-[#333336]" />

        {/* "+ 关联" button — full-row clickable item */}
        <button
          className="flex w-full items-center gap-2 rounded-[6px] px-4 py-[10px] text-[#D1D1D6] transition-colors hover:bg-[#27272A] hover:text-[#F5F5F7]"
          onClick={() => setDialogOpen(true)}
        >
          <Plus className="size-4" />
          <span>{t.dataAssets.attach}</span>
        </button>

        {/* Divider */}
        <div className="mx-0 my-2 h-px bg-[#333336]" />

        {/* Section title (matches left sidebar "最近的对话" style) */}
        <div className="px-4 py-3">
          <span className="text-xs text-[#8A8A91]">
            {t.dataAssets.title}
          </span>
        </div>

        {/* Content area — asset list */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="size-5 animate-spin text-[#8A8A91]" />
            </div>
          ) : attachedList.length === 0 ? (
            <div className="flex items-center gap-2 px-4 py-2">
              <Database className="size-4 shrink-0 text-[#8A8A91]" />
              <span className="text-sm text-[#D1D1D6]">
                {t.dataAssets.noAttachedConversations}
              </span>
            </div>
          ) : (
            <div className="flex flex-col px-4">
              {attachedList.map((attached) => (
                <div
                  key={attached.id}
                  className="group/ds-item flex items-center gap-2 rounded-[6px] px-0 py-2 transition-colors hover:bg-[#27272A]"
                >
                  <Database className="size-4 shrink-0 text-[#8A8A91]" />
                  <div className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-[#D1D1D6] transition-colors group-hover/ds-item:text-[#F5F5F7]">
                      {attached.alias ?? attached.name ?? attached.datasource_id.slice(0, 8)}
                    </span>
                    <span className="block text-[11px] text-[#8A8A91]">
                      {t.dataAssets.types[attached.type as keyof typeof t.dataAssets.types] || attached.type || "—"}
                    </span>
                  </div>
                  <button
                    className="hidden items-center justify-center rounded p-1 text-[#8A8A91] transition-colors hover:text-white group-hover/ds-item:flex"
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
              ))}
            </div>
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
