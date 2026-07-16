# 온디바이스 로컬 엔진 (클라우드+로컬 이중구조 — 제안서 차별점 ④)

평소엔 클라우드(Solar)가 채점하고, 인터넷/서버가 끊기면 **사용자 기기의
EXAONE-4.0-1.2B**가 채점을 이어받는다. 브라우저는 절을 열 때마다 로컬
어댑터에 오프라인 팩(정답 포함)을 미리 맡겨 둔다(어댑터 없으면 조용히 무시).

```
[브라우저] ─정상─→ [backend + Solar]          ← 평소
    │ POST /attempts 연결 실패 시   ↑ 절 열 때 /sync (오프라인 팩 pull)
    ▼
[adapter.py :8600] ── [llama-server :8080, EXAONE-4.0-1.2B-Q4_K_M]
```

## 실행 (사용자 기기, WSL)

```bash
./run_local.sh          # llama-server(:8080) + 어댑터(:8600)
```

- 모델·llama 바이너리는 `~/metalearn-ondevice/ondevice`(MVP 워크트리) 것을 재사용.
  다른 위치면 `ONDEVICE_MVP=/path ./run_local.sh`.
- 어댑터는 stdlib 전용(의존성 0) — python3만 있으면 된다.

## 채점 경계 (온디바이스 결정문)

| 기능 | 경로 |
|---|---|
| 콘텐츠 생성·faithfulness | 온라인 전용(Solar) — 오프라인 생성 없음 |
| mcq 채점 | 로컬, LLM 불필요(answerIndex 비교) |
| cloze 채점 | 로컬 정규화 매칭 → 불일치만 1.2B 인정판정(~7s) |
| explainBack 채점 | 1.2B 루브릭 배치 판정(1콜, ~4s) |
| 살아있는 커리큘럼(국소화·선행삽입·보충) | 온라인 전용 — 오프라인 채점엔 신호 없음 |

## 함정 노하우 (MVP에서 실측)

- EXAONE 4.0은 thinking 기본 — `enable_thinking:false` 없으면 답이 빈다.
- 시스템에 libgomp.so.1 없음 — 바이너리 폴더 것 + `LD_LIBRARY_PATH=.`.
- 작은 모델에 few-shot 예시 넣으면 그대로 베낀다 — 예시 금지.
- 첫 콜은 콜드스타트 수십 초 — 어댑터가 기동 시 워밍업 콜을 쏜다.
