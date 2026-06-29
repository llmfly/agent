import { DatabaseIcon, FilesIcon, XIcon } from "lucide-react";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GroupImperativeHandle } from "react-resizable-panels";

import { ConversationEmptyState } from "@/components/ai-elements/conversation";
import { Button } from "@/components/ui/button";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { DataSourcePanel } from "@/components/workspace/data-assets/data-source-panel";
import { env } from "@/env";
import { cn } from "@/lib/utils";

import {
  ArtifactFileDetail,
  ArtifactFileList,
  useArtifacts,
} from "../artifacts";
import { useThread } from "../messages/context";

const CHAT_ONLY = { chat: 100, datasources: 0, artifacts: 0 };
const DS_OPEN = { chat: 70, datasources: 30, artifacts: 0 };
const ARTIFACT_OPEN = { chat: 60, datasources: 0, artifacts: 40 };
const BOTH_OPEN = { chat: 50, datasources: 25, artifacts: 25 };

const ChatBox: React.FC<{ children: React.ReactNode; threadId: string }> = ({
  children,
  threadId,
}) => {
  const { thread } = useThread();
  const pathname = usePathname();
  const threadIdRef = useRef(threadId);
  const layoutRef = useRef<GroupImperativeHandle>(null);

  const {
    artifacts,
    open: artifactsOpen,
    setOpen: setArtifactsOpen,
    setArtifacts,
    select: selectArtifact,
    deselect,
    selectedArtifact,
  } = useArtifacts();

  const [dsPanelOpen, setDsPanelOpen] = useState(false);

  const [autoSelectFirstArtifact, setAutoSelectFirstArtifact] = useState(true);
  useEffect(() => {
    if (threadIdRef.current !== threadId) {
      threadIdRef.current = threadId;
      deselect();
      setDsPanelOpen(false);
    }

    // Update artifacts from the current thread
    setArtifacts(thread.values.artifacts);
  }, [
    threadId,
    deselect,
    selectArtifact,
    setArtifacts,
    thread.values.artifacts,
  ]);

  const artifactPanelOpen = useMemo(() => {
    if (env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true") {
      return artifactsOpen && artifacts?.length > 0;
    }
    return artifactsOpen;
  }, [artifactsOpen, artifacts]);

  const resizableIdBase = useMemo(() => {
    return pathname.replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  }, [pathname]);

  const anyRightPanelOpen = dsPanelOpen || artifactPanelOpen;

  useEffect(() => {
    if (layoutRef.current) {
      if (dsPanelOpen && artifactPanelOpen) {
        layoutRef.current.setLayout(BOTH_OPEN);
      } else if (dsPanelOpen) {
        layoutRef.current.setLayout(DS_OPEN);
      } else if (artifactPanelOpen) {
        layoutRef.current.setLayout(ARTIFACT_OPEN);
      } else {
        layoutRef.current.setLayout(CHAT_ONLY);
      }
    }
  }, [dsPanelOpen, artifactPanelOpen]);

  const toggleDsPanel = useCallback(() => {
    setDsPanelOpen((prev) => !prev);
  }, []);

  return (
    <ResizablePanelGroup
      id={`${resizableIdBase}-panels`}
      orientation="horizontal"
      defaultLayout={CHAT_ONLY}
      groupRef={layoutRef}
    >
      <ResizablePanel className="relative" defaultSize={100} id="chat">
        {/* DataSource toggle button in chat panel header area */}
        <div className="absolute top-0 right-0 z-40 flex items-center gap-1 p-2">
          <Button
            size="icon-sm"
            variant={dsPanelOpen ? "secondary" : "ghost"}
            className="text-muted-foreground hover:text-foreground size-7"
            onClick={toggleDsPanel}
            title="Data Sources"
          >
            <DatabaseIcon className="size-3.5" />
          </Button>
        </div>
        {children}
      </ResizablePanel>

      {/* Data Sources Panel */}
      {anyRightPanelOpen && (
        <ResizableHandle
          id={`${resizableIdBase}-ds-separator`}
          className={cn(
            "opacity-33 hover:opacity-100",
            !dsPanelOpen && "pointer-events-none opacity-0",
          )}
        />
      )}
      <ResizablePanel
        className={cn(
          "transition-all duration-300 ease-in-out",
          !dsPanelOpen && "opacity-0 overflow-hidden",
        )}
        id="datasources"
        defaultSize={200}
        minSize={200}
        maxSize={200}
      >
        <div
          className={cn(
            "h-full transition-transform duration-300 ease-in-out",
            dsPanelOpen ? "translate-x-0" : "translate-x-full",
          )}
        >
          <DataSourcePanel
            conversationId={threadId}
            open={dsPanelOpen}
            onOpenChange={setDsPanelOpen}
          />
        </div>
      </ResizablePanel>

      {/* Artifacts Panel */}
      {anyRightPanelOpen && (
        <ResizableHandle
          id={`${resizableIdBase}-artifact-separator`}
          className={cn(
            "opacity-33 hover:opacity-100",
            !artifactPanelOpen && "pointer-events-none opacity-0",
          )}
        />
      )}
      <ResizablePanel
        className={cn(
          "transition-all duration-300 ease-in-out",
          !artifactPanelOpen && "opacity-0 overflow-hidden",
        )}
        id="artifacts"
        defaultSize={0}
        minSize={20}
        maxSize={50}
      >
        <div
          className={cn(
            "h-full p-4 transition-transform duration-300 ease-in-out",
            artifactPanelOpen ? "translate-x-0" : "translate-x-full",
          )}
        >
          {selectedArtifact ? (
            <ArtifactFileDetail
              className="size-full"
              filepath={selectedArtifact}
              threadId={threadId}
            />
          ) : (
            <div className="relative flex size-full justify-center">
              <div className="absolute top-1 right-1 z-30">
                <Button
                  size="icon-sm"
                  variant="ghost"
                  onClick={() => {
                    setArtifactsOpen(false);
                  }}
                >
                  <XIcon />
                </Button>
              </div>
              {thread.values.artifacts?.length === 0 ? (
                <ConversationEmptyState
                  icon={<FilesIcon />}
                  title="No artifact selected"
                  description="Select an artifact to view its details"
                />
              ) : (
                <div className="flex size-full max-w-(--container-width-sm) flex-col justify-center p-4 pt-8">
                  <header className="shrink-0">
                    <h2 className="text-lg font-medium">Artifacts</h2>
                  </header>
                  <main className="min-h-0 grow">
                    <ArtifactFileList
                      className="max-w-(--container-width-sm) p-4 pt-12"
                      files={thread.values.artifacts ?? []}
                      threadId={threadId}
                    />
                  </main>
                </div>
              )}
            </div>
          )}
        </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
};

export { ChatBox };
