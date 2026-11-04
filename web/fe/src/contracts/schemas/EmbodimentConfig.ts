// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Name = string;
export type Version = string;
export type Domain = "sim" | "real";
export type Controller = string;
export type CameraRefHash = string | null;
/**
 * @minItems 1
 */
export type Dimensions = [ActionDimension, ...ActionDimension[]];
export type Name1 = string;
export type Group = string;
export type Masked = boolean;
/**
 * The value never varies in valid data (G1 dim 31: base height 0.74 in psi-data). A std of 0 here is expected, not a stats defect (design D4); the normalizer must keep the value unchanged. A masked dim may also be constant.
 */
export type Constant = boolean;
export type LimitLow = number | null;
export type LimitHigh = number | null;

/**
 * Configuration for an embodiment / robot embodiment.
 */
export interface EmbodimentConfig {
  name: Name;
  version?: Version;
  domain?: Domain;
  controller?: Controller;
  camera_ref_hash?: CameraRefHash;
  action_layout?: ActionLayout | null;
  meta?: Meta;
}
/**
 * This interface was referenced by `EmbodimentConfig`'s JSON-Schema
 * via the `definition` "ActionLayout".
 */
export interface ActionLayout {
  dimensions: Dimensions;
}
/**
 * This interface was referenced by `EmbodimentConfig`'s JSON-Schema
 * via the `definition` "ActionDimension".
 */
export interface ActionDimension {
  name: Name1;
  group: Group;
  masked: Masked;
  constant?: Constant;
  limit_low?: LimitLow;
  limit_high?: LimitHigh;
}
export interface Meta {
  [k: string]: unknown;
}
