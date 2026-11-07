// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type RunPlanId = string;
export type JobId = string;
export type CheckpointId = string;
export type ReleaseId = string;
export type Attempt = number;
export type Step = number;
export type Epoch = number;
export type Split = "train" | "val";
export type Loss = number | ("NaN" | "Infinity" | "-Infinity");
export type Lr = number;
export type VlmFrozen = boolean;
export type LossByChunkPos = number[];
export type GradNormVlm = number | null;
export type GradNormAction = number | null;
export type PredVarByDim = number[];
export type PredStd = number[];
export type TargetStd = number[];
export type HandOpenHist = number[];
export type VramGb = number | null;
export type Throughput = number | null;
export type WallTimeS = number;

export interface TrainingMetric {
  run_plan_id: RunPlanId;
  job_id: JobId;
  checkpoint_id: CheckpointId;
  release_id: ReleaseId;
  attempt: Attempt;
  step: Step;
  epoch: Epoch;
  split: Split;
  loss: Loss;
  lr: Lr;
  vlm_frozen: VlmFrozen;
  loss_by_group?: LossByGroup;
  loss_by_chunk_pos?: LossByChunkPos;
  grad_norm_vlm?: GradNormVlm;
  grad_norm_action?: GradNormAction;
  pred_var_by_dim?: PredVarByDim;
  pred_std?: PredStd;
  target_std?: TargetStd;
  hand_open_hist?: HandOpenHist;
  vram_gb?: VramGb;
  throughput?: Throughput;
  wall_time_s: WallTimeS;
}
export interface LossByGroup {
  [k: string]: number;
}
