import { createBrowserRouter } from "react-router-dom";

import App from "@/App";
import AppLayout from "@/AppLayout";
import { LandingPage } from "@/pages/LandingPage";
import { AuthPage } from "@/pages/AuthPage";
import { AuthCallbackPage } from "@/pages/AuthCallbackPage";
import { ProfileSetupPage } from "@/pages/ProfileSetupPage";
import { LearningPage } from "@/pages/LearningPage";
import { LibraryPage } from "@/pages/LibraryPage";
import { AnalysisPage } from "@/pages/AnalysisPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { CreateCoursePage } from "@/pages/CreateCoursePage";
import { ParsingDebugPage } from "@/pages/ParsingDebugPage";
import { CurriculumLayout } from "@/pages/CurriculumLayout";
import { CurriculumPage } from "@/pages/CurriculumPage";
import { ChapterPage } from "@/pages/ChapterPage";
import { FormativePage } from "@/pages/FormativePage";
import { ReviewPage } from "@/pages/ReviewPage";
import { DiagnosticPage } from "@/pages/DiagnosticPage";
import { SectionPage } from "@/pages/SectionPage";
import { QuizPage } from "@/pages/QuizPage";

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
  // OAuth 착지점. 제공자 → 백엔드 → 여기(#token=…)로 온다. 셸이 없다 —
  // 토큰을 저장하고 곧바로 /library로 넘어가는 통과 지점이라 사이드바가 한 번
  // 깜빡일 이유가 없다.
  { path: "/auth/callback", element: <AuthCallbackPage /> },
  // 학습 화면 — 자체 헤더를 가진 전체화면 3컬럼 (셸 밖)
  { path: "/learning", element: <LearningPage /> },
  {
    // 로그인 후 셸: 좌측 사이드바 + 본문
    element: <AppLayout />,
    children: [
      { path: "library", element: <LibraryPage /> },
      { path: "quiz", element: <QuizPage /> }, // 문제은행 — 학습과 분리된 객관 페이지 (docs/QUIZ.md)
      { path: "analysis", element: <AnalysisPage /> },
      { path: "settings", element: <SettingsPage /> },
      // 커리큘럼 — 자료 고르기(목차 없음). 여기까지가 셸 안이다
      { path: "curriculum", element: <CurriculumPage /> },
    ],
  },
  {
    // 자료 하나를 열면 **좌측에 목차가 고정**되고 본문만 바뀐다.
    // 자료 개요 → 목차 하나 → 화면 하나 → 단원 평가
    //
    // ★ 셸 밖이다. 글로벌 내비(나의 책장·분석·설정 280px)와 목차(268px)가 나란히
    // 서면 내비가 본문(672px)만큼 넓어지고, 둘이 같은 일(이동)을 한다. 상단 검색도
    // 학습 중엔 나가라고 부추기는 쪽이다. 목업 학습 화면(`/learning`)도 셸 밖이다.
    //
    // ⚠️ 경계는 화면이 아니라 **자료**다. 화면 단위로 숨기면 목차 → 화면을 누를
    //    때마다 레이아웃이 280px 튄다. 목차를 고정한 이유를 스스로 깨는 셈이다.
    path: "/curriculum/:docId",
    element: <CurriculumLayout />,
    children: [
      { index: true, element: <CurriculumPage /> },
      { path: "chapters/:index", element: <ChapterPage /> },
      // 🔁 망각곡선이 불러온 화면들. 목차 밖이라 자료 아래 바로 둔다
      { path: "review", element: <ReviewPage /> },
      { path: "chapters/:index/formative", element: <FormativePage /> },
      { path: "sections/:sectionId", element: <SectionPage /> },
    ],
  },
  // 수업 생성 위저드 — 셸 없는 전체화면 집중 플로우
  { path: "/create", element: <CreateCoursePage /> },
  // 진단 — 위저드와 같은 이유로 **셸 밖 전체화면**이다. 목차를 옆에 두면
  // "아직 안 정해진 목차"를 보면서 그 목차를 정하는 꼴이 된다. 코스에만 있다
  // (선수 개념이 코스 층에서 나온다) — 자료 하나면 404를 받고 학습으로 보낸다.
  { path: "/diagnostic/:courseId", element: <DiagnosticPage /> },
  // 파싱 단계별 실행기 (개발용) — 셸 없이 단독. 배포 시 제외 대상.
  { path: "/debug/parsing", element: <ParsingDebugPage /> },
]);
