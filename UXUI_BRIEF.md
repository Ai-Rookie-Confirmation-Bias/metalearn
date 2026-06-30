# MetaLearn — 프론트 이전·디자인 작업 기준

> UXUI_ANT(정적 목업) → `frontend/`(React) 이전과, 이후 프론트 디자인 작업의 **공통 기준**.
> 목업 비교 단계는 끝났고 **ANT 안을 `frontend/`로 이식하기로 확정**됨.
> (이전 버전의 "각자 폴더에서만 / `frontend·backend` 건드리지 말 것" 규칙은 **폐기**.)

---

## 0. 제품·디자인 의도 (유지)

- **MetaLearn = AI 학습 플랫폼.** 학습 → 퀴즈/체크 → 복습 루프.
- **데이터 → 렌더가 핵심 제약.** 콘텐츠·퀴즈·인터랙티브 요소는 **정형 데이터(JSON 봉투)** 로 기술하고 프론트가 렌더한다. 서버가 HTML을 생성하지 않는다. (→ README `## 5. 공통 블록 봉투`)
- **"AI 티 안 나는" 완성도.** 레퍼런스: brilliant / Duolingo / Grammarly (영감용, 그대로 베끼지 말 것).
- **페이지 흐름:** 랜딩 → 온보딩 → (가입/로그인) → 라이브러리 → 학습 → 마이페이지. **우선순위: 온보딩·학습.**

---

## 1. 기술·구조 규약 (확정)

- **스택:** README `## 1. 기술 스택` 참조 (React 19 / Vite / TS, Tailwind CSS 4, Phosphor, clsx, Zustand, TanStack Query, Dexie).
- **CSS = Tailwind 유틸리티를 JSX에 직접.** 원본 `.css` 파일은 복사하지 않고 **녹인다.**
  - 전역 CSS는 `src/app/index.css` **1장뿐**: `@theme` 토큰 + `@keyframes` + 스크롤바 + `font-smoothing`.
  - 유틸리티로 표현 못 하는 것(3D flip, 가상요소, CSS 차트 등)만 전역 또는 co-located `.css`로.
- **아이콘:** `@phosphor-icons/react`의 **`*Icon`** 컴포넌트(예: `ArrowRightIcon`). 접미사 없는 건 deprecated.
- **상태별 스타일 분기:** `clsx` 조건부 className.
- **FSD 배치:**
  - `pages/` = **URL과 1:1**로 매핑되는 화면 조립.
  - 페이지 전용 컴포넌트 = `pages/<page>/`에 **co-locate** (URL 없음 = page 아님).
  - 여러 곳에서 **실제로 반복**될 때만 `shared/`·`features/`로 승격(**rule of three**).
- **과잉 추상화 금지.** 디자인이 아직 통일 안 됨 → 진짜 반복이 드러나기 전엔 **인라인 유지**. (지금 공용 Button 등 만들지 말 것.)

---

## 2. 페이지 이전 체크리스트 (매 페이지 반복)

이전은 **단순 복붙이 아니다.** 매 페이지 아래를 점검한다.

### 2-1. ⚠️ Tailwind preflight가 UA 기본값을 reset → 원본이 깨짐 (최빈 함정)
원본이 **브라우저 기본 스타일에 기대던** 요소는 preflight가 덮어써서 크기·모양이 바뀐다. 옮기기 전 원본 computed 값을 확인하고 **명시**할 것.
- `<button>`: 기본 **13.333px / line-height normal** → 16px / 1.5로 커짐
- `<input>` / `<textarea>`: 폰트·패딩 기본값 사라짐
- `<h1>~<h6>`: font-size·weight 전부 리셋
- `<ul>` / `<ol>` / `<li>`: list-style 제거
- → **치수가 의심되면 추측 금지. devtools Computed로 실측 후 맞춘다.** (랜딩 버튼에서 두 번 헛짚었음)

### 2-2. 상태 + 로직 환원
- `components.css`의 `.xxx.selected / .correct / .incorrect` 등 상태 클래스 → **React state + clsx**.
- `app.js`류 vanilla JS(슬라이더·타이머·진행) → **hooks**.
- `classList` / `querySelector` 같은 DOM 조작 금지, 전부 state로.

### 2-3. 데이터 → 렌더 (learning 페이지부터 필수)
- 하드코딩 데이터 지양. 공통 블록 봉투 `{id, type, conceptId, source, verified, data}`로 기술하고 `registry[type]`로 렌더. (README `## 5`)
- 지금 mock으로 만들되, 같은 형식의 실제 서버 응답으로 갈아끼울 수 있는 형태로.

### 2-4. 라우팅·반응형
- `<a href="x.html">` → `<Link to="/x">`. 아직 없는 라우트 연결 시 **빈 화면** 주의.
- 원본 브레이크포인트(900 / 768px) ≠ Tailwind 기본(md 768 / lg 1024) → `min-[900px]:` 같은 **arbitrary variant**로 재현.

---

## 3. 작업 워크플로 (Docker 기반)

- **패키지 추가 = `package.json`/lock만으론 컨테이너에 반영 안 됨** (컨테이너 `node_modules`는 익명 볼륨으로 분리). → `docker compose build frontend` (또는 `docker compose exec frontend pnpm install`) 후 사용.
- 소스 변경은 볼륨 마운트라 **HMR로 즉시 반영** (재빌드 불필요).
- 검증은 호스트 `tsc`/`build`만으로 끝내지 말고 **실제 컨테이너 + 눈으로(원본과 픽셀 대조)**.
- **페이지 단위로 끝까지**(라우트 + JSX + CSS + 동작) 완성한 뒤 다음 페이지로.

---

## 4. 진행 현황

- [x] 전역 토대 (vite alias / CSS 경로 / `@theme` 토큰 / 폰트·안티앨리어싱 / 글로벌 헤더)
- [x] 랜딩 `/` (+ `InteractiveDemo` 데모)
- [ ] **온보딩** (최우선)
- [ ] 학습 화면 (핵심 — 데이터→렌더 설계 동반)
- [ ] 라이브러리 / 마이페이지(대시보드) / focus / create_course
