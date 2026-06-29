"use client";

import {
  DatabaseIcon,
  Loader2,
  MoreHorizontalIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
  WifiOffIcon,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Empty,
  EmptyDescription,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/core/i18n/hooks";

import { useDataSources } from "./use-data-sources";

export default function DataAssetsPage() {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const { data: dataSources, isLoading, deleteMutate } = useDataSources({
    type: typeFilter === "all" ? undefined : typeFilter,
    search: search || undefined,
  });

  const handleDelete = useCallback(
    async (id: string, name: string) => {
      if (!confirm(t.dataAssets.deleteConfirm)) return;
      try {
        await deleteMutate.mutateAsync(id);
        toast.success(t.dataAssets.deleteSuccess);
      } catch {
        toast.error(t.dataAssets.deleteSuccess);
      }
    },
    [deleteMutate, t],
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t.dataAssets.title}
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            {t.dataAssets.description}
          </p>
        </div>
        <Button asChild>
          <Link href="/workspace/data-assets/new">
            <PlusIcon className="mr-2 size-4" />
            {t.dataAssets.newDataSource}
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 border-b px-6 py-3">
        <div className="relative flex-1 max-w-sm">
          <SearchIcon className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2" />
          <Input
            placeholder={t.dataAssets.searchPlaceholder}
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder={t.dataAssets.filterAll} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t.dataAssets.filterAll}</SelectItem>
            <SelectItem value="mysql">{t.dataAssets.types.mysql}</SelectItem>
            <SelectItem value="postgresql">
              {t.dataAssets.types.postgresql}
            </SelectItem>
            <SelectItem value="elasticsearch">
              {t.dataAssets.types.elasticsearch}
            </SelectItem>
            <SelectItem value="pdf">{t.dataAssets.types.pdf}</SelectItem>
            <SelectItem value="docx">{t.dataAssets.types.docx}</SelectItem>
            <SelectItem value="txt">{t.dataAssets.types.txt}</SelectItem>
            <SelectItem value="xlsx">{t.dataAssets.types.xlsx}</SelectItem>
            <SelectItem value="csv">{t.dataAssets.types.csv}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-6 py-4">
        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}>
                <CardHeader>
                  <Skeleton className="h-5 w-32" />
                  <Skeleton className="h-4 w-48" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-4 w-24" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : dataSources && dataSources.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {dataSources.map((ds) => (
              <Link key={ds.id} href={`/workspace/data-assets/${ds.id}`}>
                <Card className="hover:bg-accent/50 cursor-pointer transition-colors">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="bg-primary/10 flex size-10 items-center justify-center rounded-lg">
                          <DatabaseIcon className="text-primary size-5" />
                        </div>
                        <div>
                          <CardTitle className="text-base">
                            {ds.name}
                          </CardTitle>
                          <CardDescription className="text-xs">
                            {ds.description || ds.type.toUpperCase()}
                          </CardDescription>
                        </div>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-8"
                            onClick={(e) => e.preventDefault()}
                          >
                            <MoreHorizontalIcon className="size-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={(e) => {
                              e.preventDefault();
                              handleDelete(ds.id, ds.name);
                            }}
                          >
                            <Trash2Icon className="mr-2 size-4" />
                            {t.common.delete}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </CardHeader>
                  <CardContent className="pb-3">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline" className="text-xs">
                        {t.dataAssets.types[ds.type] || ds.type}
                      </Badge>
                      <Badge
                        variant={
                          ds.status === "ready" ? "default" : "secondary"
                        }
                        className="text-xs"
                      >
                        {ds.status === "error" && (
                          <WifiOffIcon className="mr-1 size-3" />
                        )}
                        {t.dataAssets.status[ds.status]}
                      </Badge>
                    </div>
                  </CardContent>
                  <CardFooter className="text-muted-foreground border-t pt-3 text-xs">
                    {new Date(ds.created_at).toLocaleDateString()}
                  </CardFooter>
                </Card>
              </Link>
            ))}
          </div>
        ) : (
          <Empty>
            <EmptyTitle>{t.dataAssets.emptyTitle}</EmptyTitle>
            <EmptyDescription>{t.dataAssets.emptyDescription}</EmptyDescription>
            <Button asChild>
              <Link href="/workspace/data-assets/new">
                <PlusIcon className="mr-2 size-4" />
                {t.dataAssets.newDataSource}
              </Link>
            </Button>
          </Empty>
        )}
      </div>
    </div>
  );
}
