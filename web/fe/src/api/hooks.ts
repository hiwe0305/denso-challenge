// TanStack Query hooks, one per read endpoint the screens use.
// The query key is the path, so two screens asking the same thing share a cache.
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type {
  ActionStatusRow,
  AlgoStep,
  BranchComparisonRow,
  DecisionRow,
  SyncRunRow,
  ClusterBoardRow,
  E1CurvePoint,
  HeCurvePoint,
  ClusterCard,
  CostByBranch,
  LedgerRow,
  SensitivityRow,
  DatasetReport,
  DatasetRow,
  EpisodeRow,
  EvalEpisodeRow,
  PipelineView,
  EvaluationSummary,
  FailureBoard,
  FixRate,
  FunnelRow,
  Page,
  SystemCheckRow,
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

// ---------------------------------------------------------------- M2
export const useDatasets = () => useGet<Page<DatasetRow>>("/datasets?limit=500");
export const useIntakes = () => useGet<Page<Record<string, unknown>>>("/intakes");
export const useStages = (id: string | null) =>
  useGet<PipelineView>(id ? `/datasets/${id}/stages` : null);
export const useDatasetReport = (id: string | null) =>
  useGet<DatasetReport>(id ? `/datasets/${id}/report` : null);
export const useDatasetEpisodes = (id: string | null) =>
  useGet<Page<EpisodeRow>>(id ? `/datasets/${id}/episodes?limit=500` : null);

// ---------------------------------------------------------------- M9
// The branch is meaningless without its task, so task_id is in the key (§6.4).
export const useBranches = (task: string) =>
  useGet<BranchComparisonRow[]>(`/results/branches?task_id=${task}`);
export const useHeCurve = () => useGet<HeCurvePoint[]>("/results/he-curve");
export const useE1Curve = () => useGet<E1CurvePoint[]>("/results/e1-curve");

// ---------------------------------------------------------------- M10 and the bell
/** Actions are polled: their status is set by fwsync, in another process (§6.4). */
export const useActions = () =>
  useQuery({
    queryKey: ["/actions?limit=500"],
    queryFn: () => apiGet<Page<ActionStatusRow>>("/actions?limit=500"),
    refetchInterval: 10_000,
  });
export const useDecisions = () => useGet<Page<DecisionRow>>("/decisions?limit=500");
export const useSyncRuns = () => useGet<SyncRunRow[]>("/sync/runs");
export const useRepairTicketsAll = () => useGet<RepairTicket[]>("/repair-tickets");

// ---------------------------------------------------------------- M8
export const useLedger = () => useGet<Page<LedgerRow>>("/cost/ledger?limit=500");
export const useCostByBranch = () => useGet<CostByBranch>("/cost/by-branch");
export const useSensitivity = () => useGet<SensitivityRow[]>("/cost/sensitivity");

// ---------------------------------------------------------------- M6
export const useEvaluations = () => useGet<Page<EvaluationSummary>>("/evaluations?limit=500");
export const useFunnel = (id: string | null) =>
  useGet<FunnelRow[]>(id ? `/evaluations/${id}/funnel` : null);
export const useFailures = (id: string | null) =>
  useGet<FailureBoard>(id ? `/evaluations/${id}/failures` : null);
export const useSystemChecks = (id: string | null) =>
  useGet<SystemCheckRow[]>(id ? `/evaluations/${id}/system-checks` : null);
export const useEvalEpisodes = (id: string | null) =>
  useGet<Page<EvalEpisodeRow>>(id ? `/evaluations/${id}/episodes?limit=500` : null);
