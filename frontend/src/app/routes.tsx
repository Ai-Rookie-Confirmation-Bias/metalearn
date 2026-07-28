import { createBrowserRouter } from "react-router-dom";

import App from "@/App";
import AppLayout from "@/AppLayout";
import { LandingPage } from "@/pages/LandingPage";
import { AuthPage } from "@/pages/AuthPage";
import { ProfileSetupPage } from "@/pages/ProfileSetupPage";
import { LearningPage } from "@/pages/LearningPage";
import { LibraryPage } from "@/pages/LibraryPage";
import { AnalysisPage } from "@/pages/AnalysisPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { CreateCoursePage } from "@/pages/CreateCoursePage";

// URL 기반 페이지 매핑 지도
// 두 개의 셸: App(마케팅 헤더) / AppLayout(로그인 후 사이드바). 사이드바는 고정, 본문만 교체.
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
    ],
  },
  // 학습 화면 — 자체 헤더를 가진 전체화면 3컬럼 (셸 밖)
  { path: "/learning", element: <LearningPage /> },
  {
    // 로그인 후 셸: 좌측 사이드바 + 본문
    element: <AppLayout />,
    children: [
      { path: "library", element: <LibraryPage /> },
      { path: "analysis", element: <AnalysisPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
  // 수업 생성 위저드 — 셸 없는 전체화면 집중 플로우
  { path: "/create", element: <CreateCoursePage /> },
]);
