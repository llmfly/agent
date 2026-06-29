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
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
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
      <div className="bg-sidebar text-sidebar-foreground flex size-full flex-col">
        {/* Header — title + action icons */}
        <div className="flex items-center justify-between px-4 pt-3 pb-1">
          <span className="text-base font-medium">
            {t.dataAssets.title}
          </span>
          <div className="flex items-center gap-1">
            {/* Export button */}
            <button className="text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground flex items-center justify-center rounded-md p-1.5 transition-colors">
              <Download className="size-4" />
            </button>
            {/* Collapse button */}
            <button
              className="text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground flex items-center justify-center rounded-md p-1.5 transition-colors"
              onClick={() => onOpenChange(false)}
            >
              <PanelRightClose className="size-4" />
            </button>
          </div>
        </div>

        {/* "+ 关联" button using sidebar menu styling */}
        <SidebarGroup className="pt-1 pb-0">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => setDialogOpen(true)}>
                <Plus className="size-4" />
                <span>{t.dataAssets.attach}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>

        {/* Section title using sidebar group label */}
        <SidebarGroupLabel className="px-4 py-1">
          {t.dataAssets.title}
        </SidebarGroupLabel>

        {/* Content area — asset list */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="text-sidebar-foreground/50 size-5 animate-spin" />
            </div>
          ) : attachedList.length === 0 ? (
            <div className="flex items-center gap-2 px-4 py-2">
              <Database className="text-sidebar-foreground/50 size-4 shrink-0" />
              <span className="text-sidebar-foreground/70 text-sm">
                {t.dataAssets.noAttachedConversations}
              </span>
            </div>
          ) : (
            <SidebarGroup>
              <SidebarMenu>
                {attachedList.map((attached) => (
                  <SidebarMenuItem key={attached.id}>
                    <SidebarMenuButton className="group/ds-item flex items-center gap-2">
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
                        onClick={(e) => {
                          e.preventDefault();
                          handleDetach(attached.datasource_id);
                        }}
                        disabled={detaching === attached.datasource_id}
                      >
                        {detaching === attached.datasource_id ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="size-3.5" />
                        )}
                      </button>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroup>
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
