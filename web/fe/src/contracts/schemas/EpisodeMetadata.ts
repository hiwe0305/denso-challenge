// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SourceDetail =
  ("psi_data" | "teleop_keyboard" | "teleop_pico" | "planner_wbc" | "planner_amo") | null;
export type Renderer = ("mujoco" | "isaac") | null;
export type SyntheticTier = ("S1" | "S2" | "S3" | "S4") | null;
export type BenchmarkCopyId = string | null;

export interface EpisodeMetadata {
  source_detail?: SourceDetail;
  renderer?: Renderer;
  synthetic_tier?: SyntheticTier;
  benchmark_copy_id?: BenchmarkCopyId;
}
