// MetaLearn Mock Data Store
// Defines structured onboarding and lesson data using custom JSON schemas

const ONBOARDING_QUESTIONS = [
  {
    id: "goal",
    type: "choice",
    question: "MetaLearn에 오신 것을 환영합니다! 가장 관심 있는 학습 목표는 무엇인가요?",
    options: [
      { id: "pivot", text: "AI / 개발 직군으로 커리어 전환하기", icon: "💼" },
      { id: "school", text: "학교 전공 시험 및 과제 대비", icon: "🎓" },
      { id: "curiosity", text: "개인적인 흥미 및 최신 기술 트렌드 학습", icon: "✨" },
      { id: "work", text: "실무에서 AI 툴 및 기법 활용하기", icon: "🚀" }
    ]
  },
  {
    id: "experience",
    type: "choice",
    question: "코딩이나 인공지능 관련 선행 지식 수준은 어느 정도이신가요?",
    options: [
      { id: "none", text: "아예 모르는 입문자 (비전공자)", icon: "🌱" },
      { id: "basic", text: "기초적인 코딩 개념이나 수학은 아는 수준", icon: "🛠️" },
      { id: "pro", text: "컴퓨터 전공자 또는 현직 개발자", icon: "💻" }
    ]
  },
  {
    id: "diagnostic",
    type: "quiz-choice",
    question: "간단한 진단! '지도학습(Supervised Learning)'의 주요 특징으로 가장 올바른 것은?",
    options: [
      { id: "a", text: "정답(Label)이 없는 데이터를 활용해 패턴을 탐색한다." },
      { id: "b", text: "정답(Label)이 포함된 데이터를 사용해 모델을 훈련시킨다.", correct: true },
      { id: "c", text: "에이전트가 환경과 상호작용하며 보상을 극대화하는 방식을 배운다." },
      { id: "d", text: "사람의 개입 없이 완전 무작위로 결과물을 합성한다." }
    ],
    explanation: "지도학습은 입력 데이터와 함께 각각에 대응하는 정답(레이블)을 주어 학습을 유도하는 기법입니다."
  }
];

const LIBRARY_COURSES = [
  {
    id: "deep-learning",
    title: "딥러닝 에센셜: 기초부터 실전까지",
    category: "AI & Machine Learning",
    description: "인공신경망의 원리부터 시작해 역전파, 오차 최적화, 최신 신경망 구조까지 완벽히 마스터합니다.",
    difficulty: "초급-중급",
    lessonsCount: 4,
    xpReward: 350,
    coverColor: "var(--indigo-gradient)"
  },
  {
    id: "algorithm",
    title: "알고리즘적 사고와 문제해결력",
    category: "Computer Science",
    description: "코딩 테스트 단골 유형인 재귀, 탐색, 정렬의 구조를 눈으로 보며 입체적으로 이해합니다.",
    difficulty: "초급",
    lessonsCount: 3,
    xpReward: 240,
    coverColor: "var(--violet-gradient)"
  },
  {
    id: "quantum-computing",
    title: "양자 컴퓨팅 입문",
    category: "Emerging Tech",
    description: "큐비트, 양자 중첩, 양자 얽힘 등 수학적 수식이 아닌 직관적 인터랙티브 시뮬레이션으로 이해합니다.",
    difficulty: "고급",
    lessonsCount: 5,
    xpReward: 500,
    coverColor: "var(--emerald-gradient)"
  }
];

const DETAILED_LESSONS = {
  "deep-learning": [
    {
      id: "dl-lesson-1",
      title: "신경망과 활성화 함수의 역할",
      xp: 100,
      pages: [
        {
          id: "dl-p1",
          type: "content",
          title: "1. 인공 뉴런(Neuron) 이해하기",
          body: `인공신경망의 가장 기본 단위인 **퍼셉트론(Perceptron)**은 사람 뇌의 뉴런을 모사하여 만들어졌습니다.
          입력값(X)에 가중치(Weight)를 곱하고 편향(Bias)을 더한 값이 임계점을 넘어야 신호가 출력됩니다.
          
          아래의 가중치 슬라이더를 조절하며, 입력 신호와 가중치가 뉴런의 총합 계산 및 출력 값에 어떻게 기여하는지 실시간으로 관찰해 보세요.`,
          interactive: {
            type: "neuron-simulation",
            label: "인공 뉴런 가중치 튜닝 실험",
            inputs: [1.2, -0.8],
            defaultWeights: [0.5, 1.2],
            bias: -0.2
          }
        },
        {
          id: "dl-p2",
          type: "quiz-choice",
          title: "2. 비선형성의 도입",
          question: "인공 뉴런이 선형 계산(가중치 합) 후에 반드시 거쳐가야 하는, '비선형성(Non-linearity)'을 부여하는 함수는 무엇일까요?",
          options: [
            { id: "a", text: "항등 함수 (Identity Function)" },
            { id: "b", text: "활성화 함수 (Activation Function)", correct: true },
            { id: "c", text: "상실 함수 (Loss Function)" },
            { id: "d", text: "비용 함수 (Cost Function)" }
          ],
          explanation: "활성화 함수(예: Sigmoid, ReLU)는 출력에 비선형성을 제공하여 신경망이 단순한 선형 회귀를 넘어 복잡한 패턴을 모방하고 학습할 수 있도록 돕습니다."
        },
        {
          id: "dl-p3",
          type: "quiz-match",
          title: "3. 신경망 핵심 키워드 매칭",
          question: "다음 인공지능 용어와 설명이 올바르게 일치하도록 짝을 맞춰 보세요.",
          pairs: [
            { left: "가중치 (Weight)", right: "신호의 중요도 및 기여도를 결정하는 곱해지는 수치", id: "m1" },
            { left: "편향 (Bias)", right: "뉴런이 활성화되기 쉬운지 조절하는 더해지는 상수", id: "m2" },
            { left: "활성화 함수 (Activation)", right: "선형 결합 값을 최종 출력 신호로 변환하는 활성화 판단기", id: "m3" }
          ]
        },
        {
          id: "dl-p4",
          type: "quiz-sort",
          title: "4. 뉴런의 순방향 전파 단계",
          question: "뉴런에 입력이 들어와 결과가 계산되고 나가는 순방향 전파(Forward Propagation) 순서를 올바르게 배치하세요.",
          items: [
            { id: "s1", text: "각 입력 노드에 해당하는 입력값(X)이 도달한다." },
            { id: "s2", text: "입력값(X)에 가중치(W)를 곱한 후 모두 합산한다." },
            { id: "s3", text: "합산된 결과값에 편향(Bias)을 더한다." },
            { id: "s4", text: "최종 결과값을 활성화 함수(Activation Function)에 통과시켜 출력한다." }
          ]
        },
        {
          id: "dl-p5",
          type: "milestone",
          title: "축하합니다! 첫 레슨 완료 🎉",
          body: `뉴런의 수학적 모델링부터 활성화 함수, 그리고 순방향 계산 흐름까지 완벽히 마스터하셨습니다!
          
          **학습 요약:**
          - 뉴런은 입력에 가중치를 곱하고 편향을 합쳐 최종 활성화를 거칩니다.
          - 활성화 함수는 신경망에 비선형성을 부여하여 깊은 학습이 가능하도록 만드는 핵심 키입니다.
          
          다음 단계에서는 이 모델이 어떻게 스스로 학습하는지 알려주는 **'역전파(Backpropagation)'** 개념을 배웁니다. 준비가 되었다면 학습을 완료해 보세요.`
        }
      ]
    }
  ],
  "algorithm": [
    {
      id: "alg-lesson-1",
      title: "이진 탐색(Binary Search)과 분할 정복",
      xp: 80,
      pages: [
        {
          id: "alg-p1",
          type: "content",
          title: "1. 이진 탐색의 직관적 원리",
          body: `정렬되어 있는 리스트에서 특정 값을 찾을 때, 처음부터 하나씩 찾는 선형 탐색은 시간이 오래 걸립니다.
          **이진 탐색(Binary Search)**은 리스트의 중간값을 선택해 찾으려는 값과 비교하고, 찾는 범위의 절반을 날려버리는 분할 정복 기법입니다.
          
          아래 시뮬레이터에서 정렬된 배열 중 찾고자 하는 Target을 선택하고 '탐색 단계 실행'을 클릭하여 탐색 과정을 시각적으로 확인해 보세요.`,
          interactive: {
            type: "binary-search-simulation",
            label: "이진 탐색 단계별 가시화",
            array: [12, 23, 35, 47, 58, 62, 79, 88, 95],
            defaultTarget: 79
          }
        },
        {
          id: "alg-p2",
          type: "quiz-choice",
          title: "2. 시간 복잡도 이해",
          question: "N개의 아이템이 정렬되어 있을 때, 이진 탐색의 최악의 경우(Worst-case) 시간 복잡도는 무엇일까요?",
          options: [
            { id: "a", text: "O(N)" },
            { id: "b", text: "O(N log N)" },
            { id: "c", text: "O(log N)", correct: true },
            { id: "d", text: "O(1)" }
          ],
          explanation: "이진 탐색은 한 번 탐색할 때마다 남은 대상의 크기가 절반(1/2)으로 줄어들므로 시간 복잡도는 O(log N)이 됩니다."
        },
        {
          id: "alg-p3",
          type: "quiz-match",
          title: "3. 탐색 및 알고리즘 용어 매칭",
          question: "탐색 유형과 관련 개념을 바르게 연결해 보세요.",
          pairs: [
            { left: "선형 탐색", right: "처음부터 끝까지 요소를 차례대로 하나씩 비교하는 탐색", id: "am1" },
            { left: "이진 탐색", right: "정렬된 데이터를 반씩 쪼개 가며 중앙값과 대조하는 탐색", id: "am2" },
            { left: "정렬 (Sorting)", right: "이진 탐색을 사용하기 위해 데이터가 선행해서 갖춰야 할 상태", id: "am3" }
          ]
        },
        {
          id: "alg-p4",
          type: "quiz-sort",
          title: "4. 이진 탐색 루프 단계",
          question: "이진 탐색 알고리즘의 내부 한 사이클(Iteration)의 수행 흐름을 알맞게 정렬해 보세요.",
          items: [
            { id: "s1", text: "검색 범위의 시작(Left)과 끝(Right)의 중간 인덱스(Mid)를 계산한다." },
            { id: "s2", text: "중간 위치(Mid)의 원소와 타겟(Target) 원소의 크기를 비교한다." },
            { id: "s3", text: "타겟이 작으면 Right 포인터를 Mid-1로, 크면 Left 포인터를 Mid+1로 변경한다." },
            { id: "s4", text: "Left가 Right보다 커지거나 값을 발견할 때까지 루프를 반복한다." }
          ]
        },
        {
          id: "alg-p5",
          type: "milestone",
          title: "이진 탐색 단원 격파! 🎯",
          body: `이진 탐색의 핵심 흐름과 수학적 효율성에 대해 터득하셨습니다!
          
          **학습 요약:**
          - 이진 탐색은 반드시 데이터가 **정렬**되어 있어야만 사용할 수 있습니다.
          - 매 단계 대상을 절반씩 줄여 나가므로 데이터가 커질수록 선형 탐색 대비 엄청난 속도 차이를 보입니다.`
        }
      ]
    }
  ],
  "quantum-computing": [
    {
      id: "qc-lesson-1",
      title: "큐비트와 양자 중첩의 직관",
      xp: 120,
      pages: [
        {
          id: "qc-p1",
          type: "content",
          title: "1. 0과 1의 경계를 허물다",
          body: `고전 컴퓨터의 최소 단위인 비트(Bit)는 0 또는 1의 상태 중 하나만 가질 수 있습니다.
          하지만 **큐비트(Qubit)**는 0과 1이 동시에 공존할 수 있는 **'양자 중첩(Superposition)'** 상태를 가집니다.
          
          아래 구체 시뮬레이터에서 큐비트가 |0⟩ 상태일 확률을 슬라이더로 조절하며, 큐비트 상태 벡터 |ψ⟩ = α|0⟩ + β|1⟩ 의 기하학적 확률 분포 변화를 확인해 보세요.`,
          interactive: {
            type: "quantum-qubit-simulation",
            label: "Bloch Sphere 2D 확률 투영기",
            defaultProb0: 50
          }
        },
        {
          id: "qc-p2",
          type: "quiz-choice",
          title: "2. 측정(Measurement)의 법칙",
          question: "양자 중첩 상태인 큐비트를 현실 세계에서 관측(측정)하면 큐비트는 어떻게 변할까요?",
          options: [
            { id: "a", text: "여전히 중첩 상태를 온전히 유지한다." },
            { id: "b", text: "0 또는 1 중 하나의 고전적인 비트 상태로 붕괴(Collapse)한다.", correct: true },
            { id: "c", text: "완전히 파괴되어 아무 신호도 감지되지 않는다." },
            { id: "d", text: "동시에 두 가지 값의 결과를 모두 출력해 반환한다." }
          ],
          explanation: "양자역학에서 관측하기 전까지는 중첩 상태로 존재하던 큐비트가, 측정 과정을 거치는 순간 확률에 따라 0 또는 1이라는 고전적인 하나의 값으로 결정(붕괴)됩니다."
        },
        {
          id: "qc-p3",
          type: "quiz-match",
          title: "3. 양자 역학 기초 정의",
          question: "양자 컴퓨팅의 주요 현상과 정의를 바르게 짝지어 보세요.",
          pairs: [
            { left: "중첩 (Superposition)", right: "0과 1 상태가 관측되기 전에 동시에 확률적으로 존재하는 상태", id: "qm1" },
            { left: "얽힘 (Entanglement)", right: "두 큐비트가 아무리 멀리 떨어져 있어도 서로 결합되어 상호 작용하는 현상", id: "qm2" },
            { left: "붕괴 (Collapse)", right: "측정하는 순간 중첩이 소멸되어 하나의 고유값으로 결정되는 현상", id: "qm3" }
          ]
        },
        {
          id: "qc-p4",
          type: "quiz-sort",
          title: "4. 양자 연산 및 알고리즘 순서",
          question: "양자 회로(Quantum Circuit)에서 계산을 하고 결과를 끄집어내는 단계를 알맞은 시간 순서로 정렬해 보세요.",
          items: [
            { id: "s1", text: "큐비트를 일정한 초기 상태(|0⟩)로 세팅(Initialize)한다." },
            { id: "s2", text: "Hadamard(H) 게이트를 적용해 큐비트들을 중첩 상태로 만든다." },
            { id: "s3", text: "양자 논리 게이트들을 거치며 병렬 연산을 수행한다." },
            { id: "s4", text: "최종 측정(Measurement)을 가해 결과를 고전적인 0과 1 비트로 기록한다." }
          ]
        },
        {
          id: "qc-p5",
          type: "milestone",
          title: "양자 컴퓨팅 첫걸음 성공! 🌌",
          body: `양자 중첩과 상태 벡터, 그리고 측정에 따른 상태 붕괴 이론까지 모두 이해하셨습니다!
          
          **학습 요약:**
          - 큐비트는 관측 전에 0과 1이 확률적인 상태의 선형 조합으로 공존합니다.
          - 측정하는 행위 자체가 큐비트의 상태를 한 방향으로 고정시키는 붕괴를 일으킵니다.`
        }
      ]
    }
  ]
};

// Exporting to make it accessible to other scripts natively without module builders (SPA approach)
window.MetaLearnData = {
  onboardingQuestions: ONBOARDING_QUESTIONS,
  libraryCourses: LIBRARY_COURSES,
  detailedLessons: DETAILED_LESSONS
};
