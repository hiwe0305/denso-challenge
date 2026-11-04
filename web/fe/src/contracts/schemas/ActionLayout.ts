// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

/**
 * @minItems 1
 */
export type Dimensions = [ActionDimension, ...ActionDimension[]];
export type Name = string;
export type Group = string;
export type Masked = boolean;
/**
 * The value never varies in valid data (G1 dim 31: base height 0.74 in psi-data). A std of 0 here is expected, not a stats defect (design D4); the normalizer must keep the value unchanged. A masked dim may also be constant.
 */
export type Constant = boolean;
export type LimitLow = number | null;
export type LimitHigh = number | null;

export interface ActionLayout {
  dimensions: Dimensions;
}
/**
 * This interface was referenced by `ActionLayout`'s JSON-Schema
 * via the `definition` "ActionDimension".
 */
export interface ActionDimension {
  name: Name;
  group: Group;
  masked: Masked;
  constant?: Constant;
  limit_low?: LimitLow;
  limit_high?: LimitHigh;
}
