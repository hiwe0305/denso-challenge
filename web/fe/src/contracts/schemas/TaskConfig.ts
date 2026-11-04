// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type TaskId = string;
export type Version = string;
export type Family = string;
export type NSteps = number;
export type Version1 = string;
export type Name = string;
export type Type = string;
export type Description = string;
export type Bounds = number[] | null;
export type Fields = ConditionFieldSpec[];
export type StageNo = number;
export type Name1 = string;
export type FailureClass = ("approach" | "grasp" | "carry" | "place" | "balance") | null;
export type Stages = StageSpecConfig[];
export type Code = string;
export type Description1 = string;
export type FailureClass1 = ("approach" | "grasp" | "carry" | "place" | "balance") | null;
export type FailureKinds = FailureKindSpecConfig[];

/**
 * Task configuration including ConditionSchema and failure classes.
 */
export interface TaskConfig {
  task_id: TaskId;
  version?: Version;
  family?: Family;
  n_steps?: NSteps;
  condition_schema?: ConditionSchemaConfig;
  stages?: Stages;
  failure_kinds?: FailureKinds;
  meta?: Meta;
}
/**
 * Schema for condition vector / map.
 *
 * This interface was referenced by `TaskConfig`'s JSON-Schema
 * via the `definition` "ConditionSchemaConfig".
 */
export interface ConditionSchemaConfig {
  version?: Version1;
  fields?: Fields;
}
/**
 * Specification of one field in a ConditionSchema.
 *
 * This interface was referenced by `TaskConfig`'s JSON-Schema
 * via the `definition` "ConditionFieldSpec".
 */
export interface ConditionFieldSpec {
  name: Name;
  type?: Type;
  description?: Description;
  bounds?: Bounds;
}
/**
 * Specification of one task step / stage.
 *
 * This interface was referenced by `TaskConfig`'s JSON-Schema
 * via the `definition` "StageSpecConfig".
 */
export interface StageSpecConfig {
  stage_no: StageNo;
  name: Name1;
  failure_class?: FailureClass;
}
/**
 * Specification of a failure code and its common failure class.
 *
 * This interface was referenced by `TaskConfig`'s JSON-Schema
 * via the `definition` "FailureKindSpecConfig".
 */
export interface FailureKindSpecConfig {
  code: Code;
  description: Description1;
  failure_class?: FailureClass1;
}
export interface Meta {
  [k: string]: unknown;
}
