// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Name = string;
export type Version = string;
export type ResourceType = string;
export type Unit = string;
export type UsdPerUnit = number;
export type HumanHoursPerUnit = number;
export type IsAssumption = boolean;
export type Note = string;
export type Rates = PriceRateConfig[];

/**
 * Pricebook configuration containing resource cost rates.
 */
export interface PriceBookConfig {
  name: Name;
  version?: Version;
  rates?: Rates;
  meta?: Meta;
}
/**
 * Rate specification for a single resource type.
 *
 * This interface was referenced by `PriceBookConfig`'s JSON-Schema
 * via the `definition` "PriceRateConfig".
 */
export interface PriceRateConfig {
  resource_type: ResourceType;
  unit: Unit;
  usd_per_unit: UsdPerUnit;
  human_hours_per_unit?: HumanHoursPerUnit;
  is_assumption?: IsAssumption;
  note?: Note;
}
export interface Meta {
  [k: string]: unknown;
}
