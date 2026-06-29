"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDataSource,
  deleteDataSource,
  listDataSources,
  updateDataSource,
} from "@/core/datasource/api";
import type { DataSource, DataSourceCreateRequest, DataSourceUpdateRequest } from "@/core/datasource/types";

export function useDataSources(params?: { type?: string; search?: string }) {
  const queryClient = useQueryClient();

  const query = useQuery<DataSource[]>({
    queryKey: ["data-sources", params],
    queryFn: () => listDataSources(params),
  });

  const createMutate = useMutation({
    mutationFn: (req: DataSourceCreateRequest) => createDataSource(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data-sources"] });
    },
  });

  const updateMutate = useMutation({
    mutationFn: ({ id, req }: { id: string; req: DataSourceUpdateRequest }) =>
      updateDataSource(id, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data-sources"] });
    },
  });

  const deleteMutate = useMutation({
    mutationFn: (id: string) => deleteDataSource(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data-sources"] });
    },
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    createMutate,
    updateMutate,
    deleteMutate,
  };
}
