import { createBrowserRouter } from "react-router-dom";

import App from "@/App";
import { LandingPage } from "@/pages/LandingPage";
import { AuthPage } from "@/pages/AuthPage";
import { ProfileSetupPage } from "@/pages/ProfileSetupPage";
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
      { path: "login", element: <AuthPage /> },
      // 첫 로그인 후 프로필 설정 (지금은 디자인 확인용 라우팅 — 실제 진입은 OAuth 붙을 때)
      { path: "welcome", element: <ProfileSetupPage /> },
      { path: "learning", element: <LearningPage /> },
    ],
  },
]);
