// Vietnamese display labels. Codes stay codes in the data; only the UI translates.
import type {
  ClusterDiagnosis,
  InterventionKind,
  SyncStatus,
  SystemDiagnosis,
} from "../contracts/enums";
import type { AlgoStepStatus, BudgetResource } from "../api/types";

export const clusterDiagnosisLabel: Record<ClusterDiagnosis, string> = {
  CHUA_RO: "Chưa rõ",
  HE_THONG_CONTROLLER: "Hệ thống · controller",
  HE_THONG_RUNTIME: "Hệ thống · runtime",
  HE_THONG_DONG_BO: "Hệ thống · đồng bộ",
  HE_THONG_CALIBRATION: "Hệ thống · calibration",
  KHONG_KHA_THI: "Không khả thi",
  TRANG_THAI_DAU_XAU: "Trạng thái đầu xấu",
  NHAN_THUC: "Nhận thức",
  NGOAI_MIEN: "Ngoài miền",
  THIEU_VUNG_PHU: "Thiếu vùng phủ",
  KY_NANG_YEU: "Kỹ năng yếu",
};

export const systemDiagnosisLabel: Record<SystemDiagnosis, string> = {
  clean: "sạch",
  unknown: "chưa chấm được",
  controller: "controller",
  runtime: "runtime",
  sync: "đồng bộ",
  calibration: "calibration",
  infra: "hạ tầng",
};

/** Rollout mode of a system check (DESIGN.md 0.5). `unknown` is a null `timing`. */
export const rolloutTimingLabel: Record<"sync" | "async" | "unknown", string> = {
  sync: "đồng bộ · R1, R2 ghi nhận, không quy lỗi",
  async: "bất đồng bộ · R1, R2 tính",
  unknown: "không rõ chế độ · R1, R2 tính",
};

export const interventionKindLabel: Record<InterventionKind, string> = {
  SIM_AROUND_FAILURE: "Sinh sim quanh điểm hỏng",
  TELEOP_CORRECTION: "Teleop sửa",
  RECOVERY_DATA: "Dữ liệu phục hồi",
};

export const syncStatusLabel: Record<SyncStatus, string> = {
  PENDING: "Đang chờ xuất",
  EXPORTED: "Đang đồng bộ với lõi",
  APPLIED: "Lõi đã áp dụng",
  REJECTED: "Lõi từ chối",
};

export const algoStepStatusLabel: Record<AlgoStepStatus, string> = {
  pending: "chưa chạy",
  running: "đang chạy",
  done: "xong",
  skipped: "bỏ qua",
  failed: "hỏng",
};

export const budgetLabel: Record<BudgetResource, { name: string; unit: string }> = {
  usd: { name: "Tiền", unit: "$" },
  human_minutes: { name: "Phút người", unit: "phút" },
  gpu_hours: { name: "GPU-giờ", unit: "giờ" },
};

export const checkNameLabel: Record<string, string> = {
  feasibility: "khả thi",
  localize: "khoanh vùng",
  visual: "thị giác",
  coverage: "vùng phủ",
};

/** Number formatting that never turns "not measured" into 0. */
export function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("vi-VN", { maximumFractionDigits: digits });
}

export function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("vi-VN", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "UTC",
  });
}
