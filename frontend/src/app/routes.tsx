import { createBrowserRouter } from "react-router-dom";

import App from "@/App";
import { ExperimentalLayout, LabHome } from "@/app/ExperimentalLayout";
import { LearningPage } from "@/pages/LearningPage";
import { MaterialsPage } from "@/pages/MaterialsPage";
import { DiagnosticPage } from "@/pages/DiagnosticPage";
import { CurriculumPage } from "@/pages/CurriculumPage";

// URL 기반 페이지 매핑 지도.
// `/`        → 팀원이 만든 원래 프론트(그대로 유지)
// `/lab/*`   → 이번 세션에서 추가한 임시(테스트용) 기능, 분리 보관
export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <LearningPage /> },
      {
        path: "lab",
        element: <ExperimentalLayout />,
        children: [
          { index: true, element: <LabHome /> },
          { path: "materials", element: <MaterialsPage /> },
          { path: "diagnostic", element: <DiagnosticPage /> },
          { path: "curriculum", element: <CurriculumPage /> },
        ],
      },
    ],
  },
]);
