import { createBrowserRouter } from "react-router-dom";

import App from "@/App";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { LearningPage } from "@/pages/LearningPage";

// URL 기반 페이지 매핑 지도
// 주: 가입 전 온보딩은 랜딩과 중복되어 제외. 그 위저드 껍데기는
//     CreateCoursePage.tsx(수업 생성)로 보존 — 라우트 미연결(파킹). 나중에 만들 때 여기 추가.
export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "login", element: <LoginPage /> },
      { path: "learning", element: <LearningPage /> },
    ],
  },
]);
