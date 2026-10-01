# Agent Crossing 장기 실행 성능 프로파일링

측정 시각: 2026-08-31 09:44~09:50 KST  
범위: 진단 전용. 프로세스 재시작·정지, DB 변경, 설정 변경 없음.  
중요 조건: backend는 09:41 KST에 이미 정상 종료되었으므로, 현재 수치는 **post-stop 상태**이고 과거 backend 부하는 Docker 메타데이터·회전 로그·PostgreSQL 누적 통계로 복원했다.

## 결론

컴퓨터를 느리게 만든 Agent Crossing 측 주원인은 단순히 “DB가 커졌다”가 아니라 다음 연쇄다.

1. `byeongyong`의 중복 observation memory가 비정상적으로 누적되어 전체 snapshot이 선형 팽창했다.
2. 50 tick마다 autosave가 수백 MB snapshot을 JSONB로 다시 직렬화하고, projection 테이블을 전부 삭제 후 재삽입했다.
3. `session_memory_citations.cited_memory_id` 단독 인덱스가 없어 cascade 삭제 시 대규모 반복 순차 스캔이 발생했다.
4. JSONB 한도를 넘은 뒤에도 autosave를 계속 재시도하여 실패한 대형 트랜잭션과 WAL/checkpoint I/O가 반복되었다.
5. backend에는 CPU·메모리·PID 제한이 없었고 Docker 상태에 `OOMKilled=true`가 남았다. 커지는 약 0.8GB Python/JSON payload의 다중 복사와 DB 처리로 OrbStack VM 메모리 압박이 커졌을 가능성이 높다.

단, **현재 backend 종료 후에도** OrbStack CPU가 높았던 직접 원인은 Agent Crossing이 아니다. 현재는 `fast-trade-scanner`, `local-sokoban-agent` 등 다른 실행 중 컨테이너가 CPU를 사용하고 있다.

## 원인 순위

| 순위 | 원인 | 예상 영향 | 신뢰도 | 근거 구분 |
|---:|---|---|---|---|
| 1 | 한 에이전트의 중복 memory stream 폭증 | 메모리, JSON 직렬화 CPU, snapshot 저장시간 | 매우 큼 | 직접 증거 |
| 2 | autosave의 전체 projection 삭제/재삽입 + FK 인덱스 부재 | PostgreSQL CPU·디스크 I/O·WAL | 매우 큼 | 직접 증거 + 코드 일치 |
| 3 | 실패 후에도 매 50 tick 대형 autosave 반복 | 수분간 scheduler/API 정지, 지속 I/O | 큼 | 직접 증거 |
| 4 | 무제한 backend와 OOM/OrbStack VM peak | 호스트 메모리 압박·swap·응답 불능 | 큼 | OOM 직접, peak 귀속은 중간 신뢰 추론 |
| 5 | 다른 장기 실행 컨테이너 | backend 종료 후에도 남는 CPU 사용 | 현재 큼 | 직접 post-stop 측정 |
| 6 | 오류/healthcheck 로그 | 부수적 디스크·프로세스 비용 | 작음~중간 | 직접 증거, 주원인은 아님 |

## 1. Snapshot 팽창의 직접 원인

마지막 성공한 ACTIVE session은 turn `10700`, save version `215`였다.

- DB 저장 snapshot: `157 MB` (`pg_column_size`)
- JSON text 크기: `281 MB`
- DB 전체 크기: `624 MB`
- `game_sessions` 총 크기: `412 MB`이며 대부분 TOAST (`412 MB`)
- snapshot top-level 중 `characters`: 저장 `252 MB`, JSON text `279 MB`
- `position_history` 5,000개: `1.3 MB`; `dashboard_events` 500개: `1.1 MB`

즉 position/dashboard가 아니라 character memory가 용량을 지배한다.

| agent | memory 수 | memory 저장 크기 | JSON text | distinct content | 중복 행 |
|---|---:|---:|---:|---:|---:|
| byeongyong | 10,265 | 203 MB | 225 MB | 224 | **10,041** |
| minji | 494 | 9.9 MB | 11 MB | 494 | 0 |
| yongjun | 476 | 9.5 MB | 10 MB | 476 | 0 |
| sujin | 422 | 8.4 MB | 9.3 MB | 422 | 0 |
| woosik | 411 | 8.2 MB | 9.0 MB | 411 | 0 |
| haeun | 406 | 8.1 MB | 8.9 MB | 406 | 0 |
| wonjun | 242 | 4.8 MB | 5.3 MB | 242 | 0 |

`byeongyong` memory 중 10,239개가 OBSERVATION이며 평균 content는 23자에 불과하다. 각 1024차원 embedding의 DB 저장 크기는 평균 4,100 bytes지만 snapshot JSON에서는 float 배열 텍스트로 훨씬 크게 직렬화된다. 짧은 내용의 동일 observation을 embedding과 함께 계속 복제한 것이 핵심 팽창원이다.

실패 로그가 남긴 payload 문자 수는 다음처럼 계속 증가했다.

- turn 27,500: `731,772,699 chars`
- turn 29,000: `771,160,087 chars`
- turn 29,900: `795,187,992 chars`

2,400 turn 동안 약 63.4M chars 증가, 즉 약 **26 KB/turn**이다. 마지막 성공본 turn 10,700의 281MB와도 같은 선형 증가 경향을 보인다.

## 2. Autosave write amplification

설정은 `SESSION_AUTOSAVE_TICK_INTERVAL=50`이다. 저장 경로는 매번 다음을 수행한다.

- `record.snapshot = state.model_dump(mode="json")`로 전체 runtime state를 JSONB 갱신
- `_delete_projection()`으로 session projection 전체 삭제
- `_write_projection()`으로 character, plan, memory, citation, position, cognitive log, relationship을 전체 재삽입

PostgreSQL 누적 통계는 2026-08-27 00:12 UTC 리셋 이후 다음과 같다.

- `15,789,742` attempted INSERT
- `37,808,151` attempted DELETE
- `65 GB` WAL
- WAL buffer full `6,512,132`회
- checkpoint buffers `4,222,833`, backend buffers `9,683,220`
- Agent Crossing PostgreSQL 컨테이너 누적 Block I/O: **407 GB read / 262 GB write**
- 누적 network I/O: `274 GB receive / 151 GB send`

DB의 현재 실데이터가 624MB인데 수백 GB I/O가 발생했으므로, 용량 자체보다 반복 rewrite가 문제다. 실패 트랜잭션도 PostgreSQL 통계의 tuple 작업과 WAL 비용을 남길 수 있다.

특히 `session_memory_citations`는 다음 비정상 통계를 보였다.

- sequential scans: `6,277,018`
- tuples read by sequential scans: **9,509,571,970**
- 현재 live rows: `1,629`

`session_memory_citations` PK는 `(memory_id, cited_memory_id)`이므로 `memory_id` cascade에는 쓸 수 있지만, 별도 FK인 `cited_memory_id`로 cascade 확인/삭제할 단독 인덱스가 없다. character 삭제 → memory cascade → citation cascade 경로가 95억 tuple read와 일치한다. 이것은 전체 rewrite 설계와 결합된 가장 강한 DB 병목 증거다.

## 3. 실패 반복과 응답 정지

- 최초 관측 autosave 한도 실패: `2026-08-28 02:38:15 UTC`
- backend 로그 집계: autosave failure `384`회, JSONB limit 관련 라인 `768`개
- PostgreSQL 로그 집계: JSONB limit error `382`회
- 마지막 저장 성공은 2026-08-28 02:28 UTC 이후 갱신되지 않아 save version이 `215`에 고정
- 실패 시 `268435455 bytes` JSONB object/array element 한도를 초과

대형 실패 1회의 처리시간도 증가했다. 로그 parameter의 저장 시작 시각과 예외 시각 차이는 대략:

- turn 27,500: 약 `133초`
- turn 29,900: 약 `220초`

저장 함수는 stream과 scheduler를 중지하고 이 작업을 기다리므로, autosave 한 번마다 수분 동안 world API/healthcheck가 응답하지 않을 수 있다. 종료 직전 healthcheck는 `TimeoutError`였고 `FailingStreak=2454`; 마지막 확인된 `/world/state` 200 응답은 2026-08-30 15:46:52 UTC였다.

PostgreSQL 로그에서도 약 60MB WAL 거리와 함께 buffer의 56~58%를 쓰는 checkpoint가 반복되며, 각 checkpoint write 시간이 약 `269초`였다. 로그 표본 집계상 heavy checkpoint는 297회였다.

## 4. 메모리와 OOM

Docker metadata:

- backend 실행: 2026-08-27 00:12 UTC ~ 2026-08-31 00:41 UTC
- 최종 종료 코드: `0` (사용자 종료는 graceful)
- `OOMKilled=true`
- `RestartCount=0`
- CPU quota `0`, memory limit `0`, PID limit 없음

`OOMKilled=true`는 컨테이너 실행 기간 중 OOM 상태가 기록됐다는 직접 증거다. 다만 Docker event history가 남아 있지 않아 정확한 OOM 시각과 당시 RSS는 복구할 수 없다. 최종 `ExitCode=0`은 이번 사용자 종료가 정상 종료였다는 뜻이며 OOM 기록을 부정하지 않는다.

약 795MB snapshot을 Python 모델 → dict/list → psycopg JSON 인코딩 → PostgreSQL JSONB 파싱으로 넘기는 동안 동일 데이터의 복수 표현이 동시에 존재할 수 있다. 따라서 실제 peak memory는 payload 크기보다 상당히 컸을 가능성이 높다. 이는 강한 추론이지만 당시 per-process RSS 시계열은 없어 정확한 배수는 알 수 없다.

OrbStack Helper는 같은 VM launch 이후:

- 현재 physical footprint: `7.7 GB`
- peak physical footprint: `19.3 GB`
- host `ps` 순간값: 약 `9.9 GB RSS`, `202% CPU`

이 peak는 Agent Crossing을 포함한 **모든 OrbStack 컨테이너의 합계**이므로 19.3GB 전체를 backend에 귀속할 수는 없다.

## 5. 현재 post-stop 상태

현재 macOS memory pressure는 건강하다.

- 물리 RAM: `64 GiB`
- `memory_pressure`: free percentage `91%`
- swap: `3.0 GiB` 중 `1.48 GiB` 사용
- VM cumulative swapin/swapout 수치는 54일 uptime 전체 누적이므로 이번 사건에 귀속 불가

Agent Crossing 현재 자원:

- backend: stopped
- PostgreSQL: `0.00% CPU`, 약 `135~147 MiB`
- frontend: 대체로 `0.29~0.30% CPU`, 약 `32~33 MiB` (한 표본 4.97%)

3회 짧은 Docker 표본에서 다른 컨테이너는:

- `local-sokoban-agent`: `41.7~43.4% CPU`, 약 `337 MiB`
- `fast-trade-scanner`: `25.4~98.6% CPU`, 약 `518~542 MiB`
- `raspbot_clickstack_ch`: `1.7~4.3% CPU`, 약 `1.11 GiB`, `788 PIDs`
- `local-portfolio-engine`: `2.7~7.4% CPU`

따라서 “오래 켜둔 동안”에는 Agent Crossing이 심각한 DB I/O와 메모리 압박을 만들었지만, **지금도 느리다면** 현재 CPU 원인은 주로 위의 다른 컨테이너들이다. 진단 중 DB 대형 JSON 조회와 로그 스캔도 일시적으로 host I/O/CPU에 영향을 줬으므로 해당 순간의 OrbStack `202% CPU`는 평상시 baseline으로 사용하지 않는다.

## 6. 로그/디스크

- backend json-file log rotation: `max-size=20m`, `max-file=5` (최대 약 100MB)
- PostgreSQL도 동일 rotation 설정
- backend 보존 로그: 246,918 lines
- backend traceback lines: 1,780
- Docker 전체: images `64.52 GB`, build cache `39.99 GB` 중 `30.36 GB` reclaimable

Build cache는 디스크 공간 문제일 수 있지만 RAM 저하 원인은 아니다. 로그도 주원인보다는 실패 루프의 증상이며 rotation으로 상한이 있다.

## 7. 안전한 개선 우선순위 (적용하지 않음)

1. `byeongyong`에 동일 observation이 매 tick 저장되는 생성 경로를 먼저 수정하고, semantic dedupe/rate limit 및 memory retention 정책을 둔다.
2. 268MB JSONB element에 근접하기 전에 snapshot byte budget으로 autosave를 차단하고, 동일 실패 상태에서는 매 50 tick 재시도하지 않도록 circuit breaker/backoff를 둔다.
3. full projection rewrite를 append/upsert 또는 변경분 저장으로 전환한다. 최소한 `session_memory_citations(cited_memory_id)` 인덱스를 추가해 cascade scan 폭증을 제거한다.
4. embedding을 중복 JSON snapshot에 넣지 않고 projection/전용 벡터 테이블을 authoritative store로 사용한다. snapshot에는 참조 또는 복구에 필요한 최소 상태만 둔다.
5. autosave serialization/DB write 중 world scheduler 전체를 수분 정지시키지 않도록 immutable snapshot 생성과 DB 저장 경계를 재설계한다.
6. backend에 메모리/CPU/PID limit와 관측성을 추가한다: process RSS, snapshot bytes, save duration, WAL bytes, failed-save count, memory count per agent.
7. 별도로 현재 `fast-trade-scanner`와 `local-sokoban-agent` CPU 사용 패턴을 점검한다. 이는 Agent Crossing 수정만으로 사라지지 않는다.

## 8. 증거와 한계

주요 읽기 전용 명령:

```text
vm_stat; memory_pressure; sysctl vm.swapusage
ps -axo pid,ppid,%cpu,%mem,rss,vsz,etime,comm
vmmap -summary <OrbStack Helper PID>
docker ps -a; docker stats --no-stream; docker system df
docker inspect local-agent-crossing-backend agent-crossing-postgres
docker logs --timestamps <container>
docker exec agent-crossing-postgres psql ... SELECT ...
```

확인하지 못한 것:

- backend 실행 중 CPU/RSS 시계열과 flame graph
- OOM의 정확한 시각·직접 allocation stack
- 09:41 종료 직전 in-memory state 자체(종료로 소실)
- OrbStack 19.3GB peak 중 컨테이너별 분해

따라서 과거 CPU 비율과 OOM peak의 정확한 크기는 미확정이다. 반면 중복 memory, snapshot 크기, 반복 autosave 실패, projection rewrite, 95억 tuple scan, 65GB WAL, 407/262GB block I/O는 서로 독립된 DB·로그·코드 증거가 일치하므로 주원인 판정 신뢰도는 높다.
