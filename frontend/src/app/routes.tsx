import { createBrowserRouter } from "react-router-dom";

import App from "@/App";
import { LearningPage } from "@/pages/LearningPage";

// URL 기반 페이지 매핑 지도
export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [{ index: true, element: <LearningPage /> }],
  },
]);
