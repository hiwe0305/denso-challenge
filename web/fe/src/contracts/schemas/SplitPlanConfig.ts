// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Name = string;
export type Version = number | string;
export type Start = number;
export type Stop = number;
export type AuthorRangesToAvoid = number[][];
export type NearDuplicateThresholdDDup = number;

/**
 * Configuration for dataset split rules, seed ranges, and duplicate guards.
 */
export interface SplitPlanConfig {
  name?: Name;
  version?: Version;
  seed_ranges?: SeedRanges;
  author_ranges_to_avoid?: AuthorRangesToAvoid;
  near_duplicate_threshold_d_dup?: NearDuplicateThresholdDDup;
  meta?: Meta;
}
export interface SeedRanges {
  [k: string]: SeedRange | number[];
}
/**
 * Half-open seed range [start, stop).
 *
 * This interface was referenced by `SplitPlanConfig`'s JSON-Schema
 * via the `definition` "SeedRange".
 */
export interface SeedRange {
  start: Start;
  stop: Stop;
}
export interface Meta {
  [k: string]: unknown;
}
