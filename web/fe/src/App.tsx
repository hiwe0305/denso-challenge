// Ten screens in flywheel order (DESIGN.md §6). Screens not built yet say so
// with their milestone instead of rendering an empty page.
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { FailureToData } from "./screens/FailureToData";
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
  { code: "M2", path: "/du-lieu", title: "Dữ liệu", milestone: "M3 (10/11)" },
  { code: "M3", path: "/agent-qa", title: "Agent QA/QC", milestone: "M5 (14/11)" },
  { code: "M4", path: "/release", title: "Release", milestone: "M5 (14/11)" },
  { code: "M5", path: "/huan-luyen", title: "Huấn luyện", milestone: "M5 (14/11)" },
  { code: "M6", path: "/danh-gia", title: "Đánh giá", milestone: "M3 (10/11)" },
  { code: "M7", path: "/failure-to-data", title: "Failure→Data", element: <FailureToData />, milestone: "M3 (10/11)" },
  { code: "M8", path: "/chi-phi", title: "Chi phí", milestone: "M5 (14/11)" },
  { code: "M9", path: "/ket-qua", title: "Kết quả", milestone: "M3 (10/11)" },
  { code: "M10", path: "/kiem-toan", title: "Kiểm toán", milestone: "M5 (14/11)" },
];

export function App({ apiMode }: { apiMode: "mock" | "real" }) {
  return (
    <div className="min-h-screen">
      <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-1 overflow-x-auto px-4 py-2 text-sm">
          <span className="mr-3 shrink-0 font-semibold">Data Flywheel</span>
          {screens.map((s) => (
            <NavLink key={s.code} to={s.path}
              className={({ isActive }) =>
                `shrink-0 rounded px-2 py-1 ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
              <span className="text-xs opacity-60">{s.code}</span> {s.title}
            </NavLink>
          ))}
          {apiMode === "mock" ? (
            <span className="ml-auto shrink-0 rounded bg-fuchsia-100 px-2 py-0.5 text-xs text-fuchsia-800"
              title="MSW chặn /api và trả bộ mock demo-17-11; mọi số là bịa">
              dữ liệu mock
            </span>
          ) : null}
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
