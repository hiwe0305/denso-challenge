// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type Probe = "P2";
export type CheckpointId = string;
export type DatasetSha256 = string;
export type TokenLoss = number;

export interface ProbeP2 {
  probe?: Probe;
  checkpoint_id: CheckpointId;
  dataset_sha256: DatasetSha256;
  token_loss: TokenLoss;
}
