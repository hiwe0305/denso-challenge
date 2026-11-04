// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Probe = "P3";
export type CheckpointId = string;
export type DatasetSha256 = string;
export type ErrorByChunkPos = number[];
export type HandEventOffsetSteps = number;
export type OutOfLimitDims = number[];

export interface ProbeP3 {
  probe?: Probe;
  checkpoint_id: CheckpointId;
  dataset_sha256: DatasetSha256;
  error_by_group: ErrorByGroup;
  error_by_chunk_pos: ErrorByChunkPos;
  hand_event_offset_steps: HandEventOffsetSteps;
  out_of_limit_dims: OutOfLimitDims;
}
export interface ErrorByGroup {
  [k: string]: number;
}
