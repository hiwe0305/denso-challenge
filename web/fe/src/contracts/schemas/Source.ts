// File sinh ra. Không sửa tay.
// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types

export type SiteId = string;
export type TaskId = string;
export type EmbodimentId = string;
export type SchemaVersion = string;
export type Id = string;
export type Kind = "dataset" | "checkpoint" | "video_upload" | "code";
export type Uri = string;
export type Repo = string | null;
export type Revision = string | null;
export type Path = string | null;
export type Sha256 = string;
export type License = string;
export type DataClass = "public" | "internal" | "restricted";
export type CleanForMainTask = "true" | "false" | "unknown";
export type DownloadedAt = string;

/**
 * External or ingested raw data source with lineage and provenance.
 */
export interface Source {
  site_id?: SiteId;
  task_id?: TaskId;
  embodiment_id?: EmbodimentId;
  schema_version?: SchemaVersion;
  meta?: Meta;
  id?: Id;
  kind?: Kind;
  uri: Uri;
  repo?: Repo;
  revision?: Revision;
  path?: Path;
  sha256: Sha256;
  license?: License;
  data_class?: DataClass;
  clean_for_main_task?: CleanForMainTask;
  provenance?: Provenance;
  downloaded_at: DownloadedAt;
}
export interface Meta {
  [k: string]: unknown;
}
export interface Provenance {
  [k: string]: unknown;
}
