// Ten screens in flywheel order (DESIGN.md §6). Screens not built yet say so
// with their milestone instead of rendering an empty page.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { role, setRole } from "./api/role";
import { userRole, type UserRole } from "./contracts/enums";
import { Audit } from "./screens/Audit";
import { Cost } from "./screens/Cost";
import { DataPipeline } from "./screens/DataPipeline";
import { Evaluation } from "./screens/Evaluation";
import { FailureToData } from "./screens/FailureToData";
import { Results } from "./screens/Results";
import { Bell } from "./ui/Bell";
import { EmptyState } from "./ui/components";

interface Screen {
  code: string;
  path: string;
  title: string;
  element?: JSX.Element;
  milestone: string;
}

export const screens: Screen[] = [
  { code: "M1", path: "/tong-quan", title: "Tổng quan", milestone: "M5 (14/11)" },
  { code: "M2", path: "/du-lieu", title: "Dữ liệu", element: <DataPipeline />, milestone: "M3 (10/11)" },
  { code: "M3", path: "/agent-qa", title: "Agent QA/QC", milestone: "M5 (14/11)" },
  { code: "M4", path: "/release", title: "Release", milestone: "M5 (14/11)" },
  { code: "M5", path: "/huan-luyen", title: "Huấn luyện", milestone: "M5 (14/11)" },
  { code: "M6", path: "/danh-gia", title: "Đánh giá", element: <Evaluation />, milestone: "M3 (10/11)" },
  { code: "M7", path: "/failure-to-data", title: "Failure→Data", element: <FailureToData />, milestone: "M3 (10/11)" },
  { code: "M8", path: "/chi-phi", title: "Chi phí", element: <Cost />, milestone: "M5 (14/11)" },
  { code: "M9", path: "/ket-qua", title: "Kết quả", element: <Results />, milestone: "M3 (10/11)" },
  { code: "M10", path: "/kiem-toan", title: "Kiểm toán", element: <Audit />, milestone: "M5 (14/11)" },
];

/** Role switch until sessions exist (§7.4); changing it re-reads every screen. */
function RolePicker() {
  const client = useQueryClient();
  const [value, setValue] = useState<UserRole>(role());
  return (
    <select aria-label="vai" value={value} className="rounded border border-slate-300 bg-white px-1.5 py-0.5 text-xs"
      title="Vai tạm, gửi qua X-Fw-Role tới khi có đăng nhập"
      onChange={(e) => {
        const next = e.target.value as UserRole;
        setRole(next);
        setValue(next);
        void client.invalidateQueries();
      }}>
      {userRole.map((r) => <option key={r} value={r}>{r}</option>)}
    </select>
  );
}

export function App({ apiMode }: { apiMode: "mock" | "real" }) {
  return (
    <div className="min-h-screen">
      <nav className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white px-4 py-2 text-sm">
        <span className="mr-2 shrink-0 font-semibold">Data Flywheel</span>
        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
          {screens.map((s) => (
            <NavLink key={s.code} to={s.path}
              className={({ isActive }) =>
                `shrink-0 rounded px-2 py-1 ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
              <span className="text-xs opacity-60">{s.code}</span> {s.title}
            </NavLink>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {apiMode === "mock" ? (
            <span className="rounded bg-fuchsia-100 px-2 py-0.5 text-xs text-fuchsia-800"
              title="MSW chặn /api và trả bộ mock demo-17-11; mọi số là bịa">
              dữ liệu mock
            </span>
          ) : null}
          <RolePicker />
          <Bell />
        </div>
      </nav>
      <main className="mx-auto max-w-[1500px] p-4">
        <Routes>
          <Route path="/" element={<Navigate to="/failure-to-data" replace />} />
          {screens.map((s) => (
            <Route key={s.code} path={s.path} element={s.element ?? (
              <EmptyState title={`${s.code} · ${s.title} chưa dựng`}>Hạn theo kế hoạch: mốc {s.milestone}.</EmptyState>
            )} />
          ))}
          <Route path="*" element={<EmptyState title="Không có màn hình này" />} />
        </Routes>
      </main>
    </div>
  );
}
