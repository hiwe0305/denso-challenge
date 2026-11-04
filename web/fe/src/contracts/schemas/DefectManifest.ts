// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type DatasetId = string;
export type Seed = number;
export type TargetRef = string;
export type Code = string;
export type Defects = Defect[];

export interface DefectManifest {
  dataset_id: DatasetId;
  seed: Seed;
  defects: Defects;
}
/**
 * This interface was referenced by `DefectManifest`'s JSON-Schema
 * via the `definition` "Defect".
 */
export interface Defect {
  target_ref: TargetRef;
  code: Code;
  parameters?: Parameters;
}
export interface Parameters {
  [k: string]: boolean | number | string;
}
