// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Probe = "P1";
export type CheckpointId = string;
export type DatasetSha256 = string;

export interface ProbeP1 {
  probe?: Probe;
  checkpoint_id: CheckpointId;
  dataset_sha256: DatasetSha256;
  accuracy_by_question_type: AccuracyByQuestionType;
}
export interface AccuracyByQuestionType {
  [k: string]: number;
}
