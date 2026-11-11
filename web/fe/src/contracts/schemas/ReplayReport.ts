// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type EpisodeId = string;
export type Mode = "kinematic" | "dynamic";
export type Code = string;
export type Frames = number[];
export type Detail = string;
export type Issues = ReplayIssue[];
export type HandEventOffsetSteps = number | null;
export type SimSuccess = boolean | null;

export interface ReplayReport {
  episode_id: EpisodeId;
  mode: Mode;
  issues: Issues;
  error_by_group?: ErrorByGroup;
  hand_event_offset_steps?: HandEventOffsetSteps;
  sim_success?: SimSuccess;
}
/**
 * This interface was referenced by `ReplayReport`'s JSON-Schema
 * via the `definition` "ReplayIssue".
 */
export interface ReplayIssue {
  code: Code;
  frames?: Frames;
  detail: Detail;
}
export interface ErrorByGroup {
  [k: string]: number;
}
