// TanStack Query hooks, one per read endpoint the screens use.
// The query key is the path, so two screens asking the same thing share a cache.
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type {
  AlgoStep,
  ClusterBoardRow,
  ClusterCard,
  FixRate,
  Recommendation,
  RecommendationSummary,
  RepairTicket,
} from "./types";

const useGet = <T>(path: string | null) =>
  useQuery({
    queryKey: [path],
    queryFn: () => apiGet<T>(path as string),
    enabled: path !== null,
  });

export const useRecommendations = () => useGet<RecommendationSummary[]>("/recommendations");
export const useRecommendation = (id: string | null) =>
  useGet<Recommendation>(id ? `/recommendations/${id}` : null);
export const useAlgoSteps = (id: string | null) =>
  useGet<AlgoStep[]>(id ? `/recommendations/${id}/steps` : null);
export const useClusters = (id: string | null) =>
  useGet<ClusterBoardRow[]>(id ? `/recommendations/${id}/clusters` : null);
export const useClusterCard = (clusterId: string | null) =>
  useGet<ClusterCard>(clusterId ? `/clusters/${clusterId}/card` : null);
export const useRepairTickets = (id: string | null) =>
  useGet<RepairTicket[]>(id ? `/repair-tickets?recommendation_id=${id}` : null);
export const useFixRates = () => useGet<FixRate[]>("/fix-rates");
