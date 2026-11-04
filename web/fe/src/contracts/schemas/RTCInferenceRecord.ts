// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type JobId = string;
export type TraceId = string;
export type ChunkIndex = number;
export type ObservationSentS = number;
export type ChunkReceivedS = number;
export type DelaySteps = number;
export type BufferLevel = number;
export type BoundaryJump = number;

export interface RTCInferenceRecord {
  job_id: JobId;
  trace_id: TraceId;
  chunk_index: ChunkIndex;
  observation_sent_s: ObservationSentS;
  chunk_received_s: ChunkReceivedS;
  delay_steps: DelaySteps;
  buffer_level: BufferLevel;
  boundary_jump: BoundaryJump;
}
