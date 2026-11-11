// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type TraceId = string;
export type EpisodeId = string;
export type Uid = string;
export type Mount = string;
export type Width = number;
export type Height = number;
export type Fx = number;
export type Fy = number;
export type Cx = number;
export type Cy = number;
export type Pose = number[];
/**
 * Hash of the camera reference pinned at G0, copied from the RunPlan (PO decision Q3, 3/11/2026); not a hash of this camera. R5 compares these values against that reference.
 */
export type ReferenceSha256 = string;

/**
 * One camera of a trace; one line of `camera_params.jsonl`.
 *
 * `fx`, `fy`, `cx`, `cy` are pixels at the render resolution `width` x `height`;
 * `pose` is position (m) + MuJoCo quaternion (w, x, y, z) relative to the mount body.
 * `reference_sha256` is the hash of the camera reference pinned at G0, copied from the
 * RunPlan (PO decision Q3, 3/11/2026), never a hash of the episode's own cameras.
 */
export interface CameraParams {
  trace_id: TraceId;
  episode_id: EpisodeId;
  uid: Uid;
  mount: Mount;
  width: Width;
  height: Height;
  fx: Fx;
  fy: Fy;
  cx: Cx;
  cy: Cy;
  pose: Pose;
  reference_sha256: ReferenceSha256;
}
