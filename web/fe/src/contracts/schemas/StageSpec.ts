// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Name = string;
export type FailureClass = "approach" | "grasp" | "carry" | "place" | "balance";
export type Signals = string[] | null;

export interface StageSpec {
  name: Name;
  failure_class: FailureClass;
  signals?: Signals;
}
