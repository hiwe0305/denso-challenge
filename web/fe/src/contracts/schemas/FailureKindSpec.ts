// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Kind = string;
export type FailureClass =
  "approach" | "grasp" | "carry" | "place" | "balance" | "from_failed_stage";

export interface FailureKindSpec {
  kind: Kind;
  failure_class: FailureClass;
}
