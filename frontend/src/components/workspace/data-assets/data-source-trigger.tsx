"use client";

import { DatabaseIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/workspace/tooltip";
import { useI18n } from "@/core/i18n/hooks";

import { DataSourceAttachDialog } from "./data-source-attach-dialog";

interface Props {
  conversationId: string;
  visible?: boolean;
}

export function DataSourceTrigger({ conversationId, visible = true }: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  if (!visible) return null;

  return (
    <>
      <Tooltip content={t.dataAssets.attach}>
        <Button
          className="text-muted-foreground hover:text-foreground"
          variant="ghost"
          onClick={() => setOpen(true)}
        >
          <DatabaseIcon className="size-4" />
        </Button>
      </Tooltip>
      <DataSourceAttachDialog
        conversationId={conversationId}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}
