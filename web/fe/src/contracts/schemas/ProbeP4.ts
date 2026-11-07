// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Probe = "P4";
export type CheckpointId = string;
export type ParentCheckpointId = string;
export type Probe1 = "P1";
export type CheckpointId1 = string;
export type DatasetSha256 = string;
export type Probe2 = "P3";
export type CheckpointId2 = string;
export type DatasetSha2561 = string;
export type ErrorByChunkPos = number[];
export type HandEventOffsetSteps = number;
export type OutOfLimitDims = number[];

export interface ProbeP4 {
  probe?: Probe;
  checkpoint_id: CheckpointId;
  parent_checkpoint_id: ParentCheckpointId;
  p1: ProbeP1;
  p3: ProbeP3;
}
/**
 * This interface was referenced by `ProbeP4`'s JSON-Schema
 * via the `definition` "ProbeP1".
 */
export interface ProbeP1 {
  probe?: Probe1;
  checkpoint_id: CheckpointId1;
  dataset_sha256: DatasetSha256;
  accuracy_by_question_type: AccuracyByQuestionType;
}
export interface AccuracyByQuestionType {
  [k: string]: number;
}
/**
 * This interface was referenced by `ProbeP4`'s JSON-Schema
 * via the `definition` "ProbeP3".
 */
export interface ProbeP3 {
  probe?: Probe2;
  checkpoint_id: CheckpointId2;
  dataset_sha256: DatasetSha2561;
  error_by_group: ErrorByGroup;
  error_by_chunk_pos: ErrorByChunkPos;
  hand_event_offset_steps: HandEventOffsetSteps;
  out_of_limit_dims: OutOfLimitDims;
}
export interface ErrorByGroup {
  [k: string]: number;
}
