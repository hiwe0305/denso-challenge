// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type DatasetId = string;
export type EpisodeCount = number;

export interface DatasetReport {
  dataset_id: DatasetId;
  episode_count: EpisodeCount;
  counts_by_source?: CountsBySource;
  failed_checks_by_source?: FailedChecksBySource;
}
export interface CountsBySource {
  [k: string]: number;
}
export interface FailedChecksBySource {
  [k: string]: {
    [k: string]: number;
  };
}
