import type {
  DashboardAgent,
  DashboardEvent,
  DashboardMemory,
  DashboardRelationship,
  DashboardRelationshipEvent,
  PlanItemState,
} from "@agent-crossing/shared";
import {
  Activity,
  BrainCircuit,
  ChevronRight,
  Clock3,
  Database,
  Eye,
  Footprints,
  Heart,
  ListTree,
  MessageCircle,
  Radio,
  RefreshCw,
  Sparkles,
  UserRound,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { useDashboardState } from "../hooks/useDashboardState";
import {
  dashboardSearchParams,
  parseDashboardUrlState,
  type DashboardTabId as DashboardTab,
} from "./dashboardUrlState";
import {
  planScheduleIssues,
  railEvents as selectRailEvents,
  selectedAgentEvents as selectSelectedAgentEvents,
} from "./dashboardViewModel";
import { residentPortraitUrl } from "./residentPortraits";
import "./dashboard.css";

const tabs: { id: DashboardTab; label: string }[] = [
  { id: "overview", label: "개요" },
  { id: "relationship", label: "관계" },
  { id: "memory", label: "기억" },
  { id: "plans", label: "계획" },
  { id: "reflection", label: "성찰" },
  { id: "logs", label: "진단 로그" },
];

function displayTime(value: string | null): string {
  if (!value) return "--:--";
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function displayShortTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function actionLabel(action: string): string {
  if (action.startsWith("moving_to:")) return `${action.slice(10)}로 이동 중`;
  if (action.startsWith("arrived_at_door:"))
    return `${action.slice(16)} 문 앞에 도착`;
  if (action.startsWith("inside:"))
    return `${action.slice(7)} 실내에 머무는 중`;
  if (action.startsWith("arrived_at:")) return `${action.slice(11)}에 도착`;
  if (action.startsWith("at:")) return `${action.slice(3)}에 머무는 중`;
  if (action === "planning_route") return "이동 경로 계산 중";
  return action ? `알 수 없는 상태 (${action})` : "상태 없음";
}

function planPhase(
  item: PlanItemState,
  currentTime: string | null,
): "완료" | "진행 중" | "예정" | "시간 미확인" {
  if (!currentTime) return "시간 미확인";
  const now = Date.parse(currentTime);
  if (now >= Date.parse(item.end_time)) return "완료";
  if (now >= Date.parse(item.start_time)) return "진행 중";
  return "예정";
}

function relationshipDeltaLabel(event: DashboardRelationshipEvent): string {
  const deltaItems: [string, number][] = [
    ["친숙도", event.familiarity_delta],
    ["신뢰", event.trust_delta],
    ["인간적 호감", event.affinity_delta],
    ["긴장", event.tension_delta],
    ["이성적 관심", event.romantic_interest_delta],
  ];
  const changes = deltaItems
    .filter(([, delta]) => delta !== 0)
    .map(([label, delta]) => `${label} ${Number(delta) > 0 ? "+" : ""}${delta}`)
    .join(" · ");
  return changes || "적용된 수치 변화 없음";
}

function PlanCard({
  label,
  item,
  currentTime = null,
}: {
  label: string;
  item: PlanItemState | null;
  currentTime?: string | null;
}) {
  return (
    <article className="dashboard-plan-card">
      <span>{label}</span>
      {item ? (
        <>
          <strong>{item.action_content}</strong>
          <p>{item.location}</p>
          <small>
            {displayShortTime(item.start_time)} —{" "}
            {displayShortTime(item.end_time)}
          </small>
          <em>{planPhase(item, currentTime)}</em>
        </>
      ) : (
        <p className="dashboard-empty-copy">설정된 계획 없음</p>
      )}
    </article>
  );
}

function MemoryRow({ memory }: { memory: DashboardMemory }) {
  return (
    <article
      className={`dashboard-memory-row type-${memory.node_type.toLowerCase()}`}
    >
      <div className="dashboard-memory-meta">
        <span>{memory.node_type}</span>
        <strong>중요도 {memory.importance}</strong>
        <time>{displayShortTime(memory.created_at)}</time>
      </div>
      <p>{memory.content}</p>
      <small>최근 접근 {displayTime(memory.last_accessed_at)}</small>
      {memory.citations?.length ? (
        <small>근거 기억 #{memory.citations.join(", #")}</small>
      ) : null}
    </article>
  );
}

function EventRow({ event }: { event: DashboardEvent }) {
  const primary =
    event.reply ||
    event.decision_reason ||
    event.action_summary ||
    event.silent_reason;
  return (
    <article
      className={`dashboard-event ${event.parse_failure ? "failed" : ""}`}
    >
      <div className="dashboard-event-rail">
        <span />
      </div>
      <div className="dashboard-event-content">
        <header>
          <strong>{event.agent_name}</strong>
          <span>TURN {event.turn}</span>
          <time>{displayTime(event.occurred_at)}</time>
        </header>
        <p>{primary || "발화 없이 현재 계획을 유지했습니다."}</p>
        <div className="dashboard-event-tags">
          {event.reply ? <span className="speech">대화</span> : null}
          {event.parse_failure ? (
            <span className="error">파싱 실패</span>
          ) : null}
          {event.silent_reason ? (
            <span>침묵 · {event.silent_reason}</span>
          ) : null}
        </div>
        <details>
          <summary>공개 판단 요약 보기</summary>
          <dl>
            <dt>결정 이유</dt>
            <dd>{event.decision_reason || "기록 없음"}</dd>
            <dt>행동 요약</dt>
            <dd>{event.action_summary || "기록 없음"}</dd>
          </dl>
        </details>
      </div>
    </article>
  );
}

const relationshipEventLabels: Record<string, string> = {
  DIALOGUE_COMPLETED: "대화를 마침",
  HELP_GIVEN: "도움을 줌",
  HELP_RECEIVED: "도움을 받음",
  PERSONAL_DISCLOSURE_RECEIVED: "속마음을 들음",
  COMPLIMENT_RECEIVED: "칭찬을 받음",
  PROMISE_MADE: "약속함",
  PROMISE_KEPT: "약속을 지킴",
  PROMISE_BROKEN: "약속을 어김",
  CONFLICT: "갈등이 생김",
  INSULT_RECEIVED: "모욕을 받음",
  APOLOGY_ACCEPTED: "사과를 받아들임",
  ROMANTIC_INTEREST_RECOGNIZED: "이성적 관심을 자각함",
  ROMANTIC_GESTURE_WELCOMED: "호의적인 애정 표현을 받아들임",
  ROMANTIC_BOUNDARY_SET: "연애 관계의 경계를 정함",
};

function Score({
  label,
  value,
  bipolar = false,
}: {
  label: string;
  value: number;
  bipolar?: boolean;
}) {
  const min = bipolar ? -100 : 0;
  return (
    <div className="dashboard-relationship-score">
      <div>
        <span>{label}</span>
        <strong>{value > 0 && bipolar ? `+${value}` : value}</strong>
      </div>
      <meter aria-label={`${label} ${value}`} min={min} max={100} value={value}>
        {value}
      </meter>
    </div>
  );
}

function RelationshipPanel({
  agent,
  agents,
  onSelect,
  onTargetSelect,
  initialTargetId,
}: {
  agent: DashboardAgent;
  agents: DashboardAgent[];
  onSelect: (agentId: string, targetId: string) => void;
  onTargetSelect: (targetId: string) => void;
  initialTargetId: string;
}) {
  const relationshipTargetIds = agent.relationships
    .map((item) => item.target_agent_id)
    .join("|");
  const [targetId, setTargetId] = useState(() =>
    agent.relationships.some((item) => item.target_agent_id === initialTargetId)
      ? initialTargetId
      : (agent.relationships[0]?.target_agent_id ?? ""),
  );
  useEffect(() => {
    setTargetId((currentTargetId) => {
      if (
        initialTargetId &&
        agent.relationships.some(
          (item) => item.target_agent_id === initialTargetId,
        )
      ) {
        return initialTargetId;
      }
      if (
        agent.relationships.some(
          (item) => item.target_agent_id === currentTargetId,
        )
      ) {
        return currentTargetId;
      }
      return agent.relationships[0]?.target_agent_id ?? "";
    });
  }, [agent.agent_id, initialTargetId, relationshipTargetIds]);
  const relationship =
    agent.relationships.find((item) => item.target_agent_id === targetId) ??
    agent.relationships[0] ??
    null;
  const target = relationship
    ? (agents.find((item) => item.agent_id === relationship.target_agent_id) ??
      null)
    : null;
  return (
    <section className="dashboard-panel dashboard-relationship-panel">
      <div className="dashboard-panel-title">
        <span>
          <Heart size={14} /> {agent.name}이 바라보는 관계
        </span>
        <strong>방향성 관계 · 규칙 v1</strong>
      </div>
      <p className="dashboard-relationship-note">
        현재 완료된 대화와 확정된 관계 사건이 수치를 바꿉니다. 이성적 관심은
        명시적인 애정 사건에서만 변하며, 수치는 {agent.name}의 관점에만
        적용됩니다.
      </p>
      <div className="dashboard-relationship-explorer">
        <div
          className="dashboard-relationship-targets"
          aria-label="관계 대상 목록"
        >
          {agent.relationships.map((item) => (
            <button
              type="button"
              key={item.target_agent_id}
              aria-pressed={
                item.target_agent_id === relationship?.target_agent_id
              }
              onClick={() => {
                setTargetId(item.target_agent_id);
                onTargetSelect(item.target_agent_id);
              }}
            >
              <strong>{item.target_name}</strong>
              <span>{item.status_label}</span>
              <small>
                인간적 호감 {item.metrics.affinity > 0 ? "+" : ""}
                {item.metrics.affinity} · 긴장 {item.metrics.tension}
              </small>
            </button>
          ))}
        </div>
        {relationship ? (
          <article className="dashboard-relationship-detail" aria-live="polite">
            <header>
              <div>
                <small>
                  {agent.name} → {relationship.target_name}
                </small>
                <h2>{relationship.status_label}</h2>
              </div>
              <span>REV {relationship.revision}</span>
            </header>
            <div className="dashboard-relationship-scores">
              <Score label="친숙도" value={relationship.metrics.familiarity} />
              <Score label="신뢰" value={relationship.metrics.trust} bipolar />
              <Score
                label="인간적 호감"
                value={relationship.metrics.affinity}
                bipolar
              />
              <Score label="긴장" value={relationship.metrics.tension} />
              <Score
                label="이성적 관심"
                value={relationship.metrics.romantic_interest}
              />
            </div>
            <section>
              <h3>최근 변화</h3>
              {relationship.recent_events.length ? (
                <div className="dashboard-relationship-events">
                  {relationship.recent_events.map((event) => (
                    <article key={event.id}>
                      <strong>
                        {relationshipEventLabels[event.event_type] ??
                          "관계 변화"}
                      </strong>
                      <time>{displayShortTime(event.occurred_at)}</time>
                      <p>{relationshipDeltaLabel(event)}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="dashboard-empty-copy">
                  아직 기록된 변화가 없습니다.
                </p>
              )}
            </section>
            <section>
              <h3>관계 요약</h3>
              <p className="dashboard-relationship-summary">
                {relationship.summary ?? "아직 기록된 관계 근거가 없습니다."}
              </p>
              <p className="dashboard-relationship-freshness">
                마지막 상호작용 {displayTime(relationship.last_interaction_at)}{" "}
                · 갱신 {displayTime(relationship.updated_at)}
              </p>
              <details>
                <summary>
                  관계를 뒷받침하는 기록 · 표시 {relationship.evidence.length} /
                  총 {relationship.evidence_total}개
                </summary>
                <div className="dashboard-relationship-evidence">
                  {relationship.evidence.map((evidence, index) => (
                    <article
                      key={`${evidence.source}-${evidence.memory_id ?? index}`}
                    >
                      <span>
                        {evidence.source === "persona"
                          ? "고정 성향"
                          : evidence.node_type === "REFLECTION"
                            ? "성찰"
                            : "경험 기억"}
                      </span>
                      <p>{evidence.content}</p>
                      {evidence.created_at ? (
                        <small>{displayShortTime(evidence.created_at)}</small>
                      ) : null}
                    </article>
                  ))}
                </div>
                {relationship.has_more_evidence ? (
                  <small>
                    최근 {relationship.evidence.length}개를 표시합니다. 추가
                    근거{" "}
                    {Math.max(
                      0,
                      relationship.evidence_total -
                        relationship.evidence.length,
                    )}
                    개가 있습니다.
                  </small>
                ) : null}
              </details>
            </section>
            <section className="dashboard-relationship-now">
              <h3>상대의 지금</h3>
              <dl>
                <div>
                  <dt>현재 행동</dt>
                  <dd>
                    {target
                      ? actionLabel(target.current_action)
                      : "상태 확인 불가"}
                  </dd>
                </div>
                <div>
                  <dt>현재 위치</dt>
                  <dd>{target?.current_location_path ?? "확인할 수 없음"}</dd>
                </div>
                <div>
                  <dt>목적지</dt>
                  <dd>{target?.destination ?? "목적지 없음"}</dd>
                </div>
              </dl>
            </section>
            <button
              type="button"
              className="dashboard-perspective-button"
              onClick={() =>
                onSelect(relationship.target_agent_id, agent.agent_id)
              }
            >
              {relationship.target_name}의 관점에서 보기{" "}
              <ChevronRight size={15} />
            </button>
          </article>
        ) : (
          <p className="dashboard-empty-copy">표시할 관계 대상이 없습니다.</p>
        )}
      </div>
    </section>
  );
}

function AgentOverview({ agent }: { agent: DashboardAgent }) {
  const recentThought =
    agent.bubble_kind === "thought" ? agent.bubble_text : null;
  const portraitUrl = residentPortraitUrl(agent.agent_id);
  return (
    <div className="dashboard-overview-grid">
      <section className="dashboard-panel dashboard-profile-panel">
        <div className="dashboard-panel-title">
          <span>
            <UserRound size={14} /> 프로필 · 페르소나
          </span>
          <strong>
            {agent.age}세 · {agent.gender}
          </strong>
        </div>
        <div className="dashboard-profile-layout">
          <div className="dashboard-profile-summary">
            {portraitUrl ? (
              <div className="dashboard-profile-portrait">
                <img src={portraitUrl} alt={`${agent.name}의 초상화`} />
              </div>
            ) : (
              <div
                className="dashboard-profile-portrait dashboard-portrait-fallback"
                aria-label={`${agent.name}의 초상화 없음`}
              >
                {agent.name.slice(0, 1)}
              </div>
            )}
            <dl>
              <div>
                <dt>나이</dt>
                <dd>{agent.age}세</dd>
              </div>
              <div>
                <dt>성별</dt>
                <dd>{agent.gender}</dd>
              </div>
            </dl>
            <div className="dashboard-traits" aria-label="핵심 특성">
              {agent.traits.map((trait) => (
                <span key={trait}>{trait}</span>
              ))}
            </div>
          </div>
          <div className="dashboard-persona-copy">
            <h3>고정 페르소나</h3>
            {agent.persona.length ? (
              <ul>
                {agent.persona.map((statement, index) => (
                  <li key={`${index}-${statement}`}>{statement}</li>
                ))}
              </ul>
            ) : (
              <p className="dashboard-empty-copy">
                등록된 고정 페르소나가 없습니다.
              </p>
            )}
          </div>
        </div>
      </section>
      <section className="dashboard-panel dashboard-now-panel">
        <div className="dashboard-panel-title">
          <span>
            <Activity size={14} /> 현재 상태
          </span>
          <i className="dashboard-live-dot" />
        </div>
        <h2>{actionLabel(agent.current_action)}</h2>
        <dl className="dashboard-facts">
          <div>
            <dt>현재 위치</dt>
            <dd>
              {agent.current_location_path ?? "확인할 수 없음"}
              {agent.current_location_source === "arrival"
                ? " (도착 상태 기준)"
                : ""}
            </dd>
          </div>
          <div>
            <dt>목적지</dt>
            <dd>{agent.destination ?? "목적지 없음"}</dd>
          </div>
          <div>
            <dt>타일</dt>
            <dd>
              {agent.tile_position.x}, {agent.tile_position.y}
            </dd>
          </div>
          <div>
            <dt>남은 경로</dt>
            <dd>{agent.route_remaining} tiles</dd>
          </div>
        </dl>
      </section>
      <section className="dashboard-panel dashboard-thought-panel">
        <div className="dashboard-panel-title">
          <span>
            <BrainCircuit size={14} /> 현재 표시 중인 생각
          </span>
        </div>
        <blockquote>
          {recentThought ?? "현재 화면에 표시 중인 생각이 없습니다."}
        </blockquote>
      </section>
      <section className="dashboard-panel dashboard-plan-summary">
        <div className="dashboard-panel-title">
          <span>
            <ListTree size={14} /> 실행 중인 계획
          </span>
        </div>
        <h3>
          {agent.active_minute?.action_content ?? "활성 분 단위 계획 없음"}
        </h3>
        <p>
          {agent.active_minute?.location ?? agent.destination ?? "장소 미정"}
        </p>
        {agent.current_plan_context.length ? (
          <small>배경 계획 문맥 · {agent.current_plan_context[0]}</small>
        ) : null}
      </section>
      <section className="dashboard-panel dashboard-reflection-summary">
        <div className="dashboard-panel-title">
          <span>
            <Sparkles size={14} /> 성찰 축적
          </span>
          <strong>
            {agent.reflection_status.accumulated_importance} /{" "}
            {agent.reflection_status.threshold}
          </strong>
        </div>
        <progress
          className="dashboard-progress"
          max={Math.max(1, agent.reflection_status.threshold)}
          value={agent.reflection_status.accumulated_importance}
        />
        <p>
          다음 성찰까지{" "}
          {Math.max(
            0,
            agent.reflection_status.threshold -
              agent.reflection_status.accumulated_importance,
          )}
          점 남았습니다.
        </p>
      </section>
    </div>
  );
}

export function Dashboard() {
  const {
    data,
    connection,
    error,
    lastUpdatedAt,
    isStale,
    refresh,
    setAgentEnabled,
    loadMemories,
  } = useDashboardState();
  const initialUrlState = useMemo(
    () => parseDashboardUrlState(window.location.search),
    [],
  );
  const [selectedAgentId, setSelectedAgentId] = useState<string>(
    initialUrlState.agentId,
  );
  const [tab, setTab] = useState<DashboardTab>(initialUrlState.tab);
  const [eventAgentFilter, setEventAgentFilter] = useState<string>(
    initialUrlState.railAgentFilter,
  );
  const [relationshipTargetId, setRelationshipTargetId] = useState<string>(
    initialUrlState.relationshipTargetId,
  );
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryType, setMemoryType] = useState("all");
  const [olderMemories, setOlderMemories] = useState<DashboardMemory[]>([]);
  const [memoryCursor, setMemoryCursor] = useState<number | null>(null);
  const [memoryHasMore, setMemoryHasMore] = useState(true);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [reflectionMemories, setReflectionMemories] = useState<
    DashboardMemory[]
  >([]);
  const [reflectionCursor, setReflectionCursor] = useState<number | null>(null);
  const [reflectionHasMore, setReflectionHasMore] = useState(false);
  const [reflectionLoading, setReflectionLoading] = useState(false);
  const [reflectionError, setReflectionError] = useState<string | null>(null);
  const [logQuery, setLogQuery] = useState("");
  const [logFailuresOnly, setLogFailuresOnly] = useState(false);
  const [activationPending, setActivationPending] = useState(false);
  const [activationError, setActivationError] = useState<string | null>(null);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    document.body.classList.add("dashboard-route");
    return () => document.body.classList.remove("dashboard-route");
  }, []);

  useEffect(() => {
    if (!selectedAgentId && data?.agent_activations[0]) {
      setSelectedAgentId(data.agent_activations[0].agent_id);
    }
  }, [data, selectedAgentId]);

  useEffect(() => {
    const search = dashboardSearchParams({
      agentId: selectedAgentId,
      tab,
      relationshipTargetId,
      railAgentFilter: eventAgentFilter,
    });
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${search}`,
    );
  }, [eventAgentFilter, relationshipTargetId, selectedAgentId, tab]);

  useEffect(() => {
    function restoreUrlState(): void {
      const restored = parseDashboardUrlState(window.location.search);
      setSelectedAgentId(restored.agentId);
      setTab(restored.tab);
      setRelationshipTargetId(restored.relationshipTargetId);
      setEventAgentFilter(restored.railAgentFilter);
    }
    window.addEventListener("popstate", restoreUrlState);
    return () => window.removeEventListener("popstate", restoreUrlState);
  }, []);

  const selectedActivation =
    data?.agent_activations.find(
      (activation) => activation.agent_id === selectedAgentId,
    ) ??
    data?.agent_activations[0] ??
    null;
  const selectedAgent =
    data?.agents.find(
      (agent) => agent.agent_id === selectedActivation?.agent_id,
    ) ?? null;
  const selectedAgentKey = selectedAgent?.agent_id ?? null;
  useEffect(() => {
    setOlderMemories([]);
    setMemoryCursor(null);
    setMemoryHasMore(true);
    setMemoryError(null);
  }, [memoryType, selectedAgent?.agent_id]);

  useEffect(() => {
    let cancelled = false;
    setReflectionMemories([]);
    setReflectionCursor(null);
    setReflectionHasMore(false);
    setReflectionError(null);
    if (tab !== "reflection" || !selectedAgentKey) return;
    setReflectionLoading(true);
    void loadMemories(selectedAgentKey, null, "REFLECTION")
      .then((page) => {
        if (cancelled) return;
        setReflectionMemories(page.items);
        setReflectionCursor(page.next_cursor);
        setReflectionHasMore(page.has_more);
      })
      .catch((loadError: unknown) => {
        if (cancelled) return;
        setReflectionError(
          loadError instanceof Error
            ? loadError.message
            : "성찰 목록 불러오기 실패",
        );
      })
      .finally(() => {
        if (!cancelled) setReflectionLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadMemories, selectedAgentKey, tab]);
  const railEvents = useMemo(() => {
    return selectRailEvents(data?.events ?? [], eventAgentFilter);
  }, [data?.events, eventAgentFilter]);
  const selectedAgentEvents = useMemo(() => {
    if (!selectedAgent) return [];
    const normalizedQuery = logQuery.trim().toLocaleLowerCase("ko-KR");
    return selectSelectedAgentEvents(data?.events ?? [], selectedAgent.agent_id)
      .filter((event) => !logFailuresOnly || event.parse_failure)
      .filter((event) => {
        if (!normalizedQuery) return true;
        return [
          event.reply,
          event.silent_reason,
          event.decision_reason,
          event.action_summary,
        ].some((value) =>
          value.toLocaleLowerCase("ko-KR").includes(normalizedQuery),
        );
      });
  }, [data?.events, logFailuresOnly, logQuery, selectedAgent]);
  const visibleMemories = useMemo(() => {
    const normalizedQuery = memoryQuery.trim().toLocaleLowerCase("ko-KR");
    const merged = new Map(
      [...(selectedAgent?.memories ?? []), ...olderMemories].map((memory) => [
        memory.id,
        memory,
      ]),
    );
    return [...merged.values()]
      .sort((left, right) => right.id - left.id)
      .filter(
        (memory) =>
          (memoryType === "all" || memory.node_type === memoryType) &&
          (!normalizedQuery ||
            [
              memory.content,
              memory.node_type,
              `중요도 ${memory.importance}`,
            ].some((value) =>
              value.toLocaleLowerCase("ko-KR").includes(normalizedQuery),
            )),
      );
  }, [memoryQuery, memoryType, olderMemories, selectedAgent?.memories]);
  const planIssues = useMemo(
    () => planScheduleIssues(selectedAgent?.day_plan ?? []),
    [selectedAgent?.day_plan],
  );

  function handleTabKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ): void {
    let nextIndex = index;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft")
      nextIndex = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = tabs.length - 1;
    else return;
    event.preventDefault();
    const nextTab = tabs[nextIndex];
    if (!nextTab) return;
    setTab(nextTab.id);
    tabRefs.current[nextIndex]?.focus();
  }

  async function handleActivationChange(): Promise<void> {
    if (!selectedActivation || activationPending) return;
    setActivationPending(true);
    setActivationError(null);
    try {
      await setAgentEnabled(
        selectedActivation.agent_id,
        !selectedActivation.enabled,
      );
    } catch (changeError) {
      const message =
        changeError instanceof Error
          ? changeError.message
          : "활성 상태를 변경하지 못했습니다.";
      setActivationError(
        message.includes("at least two agents")
          ? "시뮬레이션을 위해 최소 두 명의 주민은 활성 상태여야 합니다."
          : message,
      );
    } finally {
      setActivationPending(false);
    }
  }

  async function handleLoadOlderMemories(): Promise<void> {
    if (!selectedAgent || memoryLoading) return;
    setMemoryLoading(true);
    setMemoryError(null);
    try {
      const initialCursor = Math.min(
        ...selectedAgent.memories
          .filter(
            (memory) => memoryType === "all" || memory.node_type === memoryType,
          )
          .map((memory) => memory.id),
      );
      const page = await loadMemories(
        selectedAgent.agent_id,
        memoryCursor ?? (Number.isFinite(initialCursor) ? initialCursor : null),
        memoryType,
      );
      setOlderMemories((current) => [...current, ...page.items]);
      setMemoryCursor(page.next_cursor);
      setMemoryHasMore(page.has_more);
    } catch (loadError) {
      setMemoryError(
        loadError instanceof Error ? loadError.message : "기억 불러오기 실패",
      );
    } finally {
      setMemoryLoading(false);
    }
  }

  async function handleLoadOlderReflections(): Promise<void> {
    if (!selectedAgent || reflectionLoading || reflectionCursor === null)
      return;
    setReflectionLoading(true);
    setReflectionError(null);
    try {
      const page = await loadMemories(
        selectedAgent.agent_id,
        reflectionCursor,
        "REFLECTION",
      );
      setReflectionMemories((current) => [...current, ...page.items]);
      setReflectionCursor(page.next_cursor);
      setReflectionHasMore(page.has_more);
    } catch (loadError) {
      setReflectionError(
        loadError instanceof Error
          ? loadError.message
          : "성찰 목록 불러오기 실패",
      );
    } finally {
      setReflectionLoading(false);
    }
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <a className="dashboard-brand" href="/">
          <span>✦</span>
          <div>
            <strong>AGENT CROSSING</strong>
            <small>COGNITIVE OBSERVATORY</small>
          </div>
        </a>
        <div className="dashboard-world-clock">
          <Clock3 size={15} />
          <strong>{displayTime(data?.world.current_time ?? null)}</strong>
          <span>TURN {data?.world.turn ?? "--"}</span>
          <span>REV {data?.world.revision ?? "--"}</span>
        </div>
        <div
          className={`dashboard-connection ${connection}`}
          role="status"
          aria-live="polite"
        >
          <Radio size={14} />
          {connection === "live"
            ? isStale
              ? "STALE"
              : "LIVE"
            : connection === "connecting"
              ? "CONNECTING"
              : "OFFLINE"}
        </div>
        <button type="button" className="dashboard-refresh" onClick={refresh}>
          <RefreshCw size={14} /> 새로고침
        </button>
      </header>

      {error ? (
        <div className="dashboard-error" role="alert">
          {error} · 실제 runtime 연결을 다시 시도하고 있습니다.
        </div>
      ) : null}
      {data?.world.planning_error ? (
        <div className="dashboard-error" role="alert">
          일정 생성 오류 · {data.world.planning_error}
        </div>
      ) : null}
      {data?.world.cognitive_runtime_error ? (
        <div className="dashboard-error" role="alert">
          인지 runtime 오류 · {data.world.cognitive_runtime_error}
        </div>
      ) : null}
      <div className="dashboard-freshness" role="status">
        마지막 정상 갱신{" "}
        {lastUpdatedAt ? displayTime(lastUpdatedAt.toISOString()) : "--:--"}
        {data
          ? ` · 응답 생성 ${displayTime(data.world.snapshot_generated_at)}`
          : ""}
      </div>

      <div className="dashboard-layout">
        <aside className="dashboard-agent-rail">
          <div className="dashboard-rail-title">
            <Eye size={14} />
            <span>에이전트</span>
            <b>
              {data?.agents.length ?? 0}/{data?.agent_activations.length ?? 0}
            </b>
          </div>
          <div className="dashboard-agent-list">
            {(data?.agent_activations ?? []).map((activation) => {
              const agent = data?.agents.find(
                (item) => item.agent_id === activation.agent_id,
              );
              const portraitUrl = residentPortraitUrl(activation.agent_id);
              return (
                <button
                  type="button"
                  key={activation.agent_id}
                  className={`${
                    activation.agent_id === selectedActivation?.agent_id
                      ? "selected"
                      : ""
                  } ${activation.enabled ? "" : "inactive"}`}
                  aria-pressed={
                    activation.agent_id === selectedActivation?.agent_id
                  }
                  onClick={() => {
                    setSelectedAgentId(activation.agent_id);
                    setRelationshipTargetId("");
                  }}
                >
                  <span className="dashboard-avatar">
                    {portraitUrl ? (
                      <img src={portraitUrl} alt="" />
                    ) : (
                      activation.name.slice(0, 1)
                    )}
                  </span>
                  <div>
                    <strong>{activation.name}</strong>
                    <small>
                      {activation.enabled && agent
                        ? actionLabel(agent.current_action)
                        : "비활성"}
                    </small>
                  </div>
                  <ChevronRight size={15} />
                </button>
              );
            })}
          </div>
          <section className="dashboard-runtime-card">
            <span>RUNTIME</span>
            <dl>
              <div>
                <dt>Scheduler</dt>
                <dd>{data?.world.scheduler_running ? "RUNNING" : "STOPPED"}</dd>
              </div>
              <div>
                <dt>Cognitive</dt>
                <dd>{data?.world.cognitive_active ? "ACTIVE" : "IDLE"}</dd>
              </div>
              <div>
                <dt>Time step</dt>
                <dd>{data?.world.effective_time_step_seconds ?? "--"}s</dd>
              </div>
            </dl>
          </section>
        </aside>

        <section className="dashboard-main">
          <div
            className="dashboard-tabs"
            role="tablist"
            aria-label="에이전트 상세 정보"
          >
            {tabs.map((item, index) => (
              <button
                type="button"
                key={item.id}
                ref={(element) => {
                  tabRefs.current[index] = element;
                }}
                id={`dashboard-tab-${item.id}`}
                role="tab"
                aria-selected={tab === item.id}
                aria-controls={`dashboard-panel-${item.id}`}
                tabIndex={tab === item.id ? 0 : -1}
                className={tab === item.id ? "active" : ""}
                onClick={() => setTab(item.id)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
              >
                {item.label}
              </button>
            ))}
          </div>

          {!selectedAgent && selectedActivation ? (
            <section className="dashboard-empty dashboard-inactive-panel">
              <Eye size={24} />
              <h2>{selectedActivation.name}은(는) 비활성 상태입니다</h2>
              <p>게임과 새 세션에서 제외되어 있습니다.</p>
              <button
                type="button"
                role="switch"
                aria-checked={false}
                aria-busy={activationPending}
                disabled={activationPending}
                onClick={() => void handleActivationChange()}
              >
                {activationPending ? "활성화 중…" : "주민 활성화"}
              </button>
              {activationError ? (
                <p className="dashboard-activation-error" role="alert">
                  {activationError}
                </p>
              ) : null}
            </section>
          ) : !selectedAgent ? (
            <section className="dashboard-empty">
              <RefreshCw size={24} />
              <h2>
                {connection === "connecting"
                  ? "대시보드에 연결하는 중"
                  : connection === "offline"
                    ? "대시보드에 연결할 수 없음"
                    : "에이전트 runtime을 기다리는 중"}
              </h2>
              <p>
                {connection === "offline"
                  ? "네트워크와 backend 상태를 확인한 뒤 다시 시도하세요."
                  : "실제 인지 runtime이 준비되면 이 화면에 표시됩니다."}
              </p>
              {connection === "offline" ? (
                <button type="button" onClick={refresh}>
                  다시 시도
                </button>
              ) : null}
            </section>
          ) : (
            <div
              className="dashboard-tab-content"
              id={`dashboard-panel-${tab}`}
              role="tabpanel"
              aria-labelledby={`dashboard-tab-${tab}`}
              tabIndex={0}
            >
              <div className="dashboard-agent-heading">
                <div>
                  <span>{selectedAgent.agent_id}</span>
                  <h1>{selectedAgent.name}</h1>
                </div>
                <div className="dashboard-agent-controls">
                  <p>{selectedAgent.bubble_text || "현재 관찰 문장 없음"}</p>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={selectedActivation?.enabled ?? true}
                    aria-busy={activationPending}
                    disabled={activationPending}
                    onClick={() => void handleActivationChange()}
                  >
                    <span aria-hidden="true" />
                    {activationPending ? "변경 중…" : "활성"}
                  </button>
                  {activationError ? (
                    <small className="dashboard-activation-error" role="alert">
                      {activationError}
                    </small>
                  ) : null}
                </div>
              </div>
              {tab === "overview" ? (
                <AgentOverview agent={selectedAgent} />
              ) : null}
              {tab === "relationship" ? (
                <RelationshipPanel
                  agent={selectedAgent}
                  agents={data?.agents ?? []}
                  initialTargetId={relationshipTargetId}
                  onSelect={(agentId, targetId) => {
                    setSelectedAgentId(agentId);
                    setRelationshipTargetId(targetId);
                  }}
                  onTargetSelect={setRelationshipTargetId}
                />
              ) : null}
              {tab === "memory" ? (
                <section className="dashboard-panel dashboard-list-panel">
                  <div className="dashboard-panel-title">
                    <span>
                      <Database size={14} /> Memory Stream
                    </span>
                    <strong>
                      검색 결과 {visibleMemories.length}개 · 불러온{" "}
                      {
                        new Set(
                          [...selectedAgent.memories, ...olderMemories].map(
                            (memory) => memory.id,
                          ),
                        ).size
                      }
                      / 전체 {selectedAgent.memory_total}개
                    </strong>
                  </div>
                  <div className="dashboard-toolbar">
                    <input
                      value={memoryQuery}
                      onChange={(event) => setMemoryQuery(event.target.value)}
                      placeholder="불러온 기억 원문 검색"
                      aria-label="기억 검색"
                    />
                    <select
                      value={memoryType}
                      onChange={(event) => setMemoryType(event.target.value)}
                      aria-label="기억 유형 필터"
                    >
                      <option value="all">모든 유형</option>
                      <option value="OBSERVATION">관찰</option>
                      <option value="PLAN">계획</option>
                      <option value="REFLECTION">성찰</option>
                    </select>
                  </div>
                  <p className="dashboard-privacy-note">
                    기억 원문과 유형·중요도·생성 및 최근 접근 시각을 표시합니다.
                  </p>
                  <div className="dashboard-memory-list">
                    {visibleMemories.length ? (
                      visibleMemories.map((memory) => (
                        <MemoryRow
                          key={`${memory.node_type}-${memory.id}`}
                          memory={memory}
                        />
                      ))
                    ) : (
                      <p className="dashboard-empty-copy">
                        {selectedAgent.memory_total === 0
                          ? "저장된 기억이 없습니다."
                          : selectedAgent.memory_has_more
                            ? "현재 불러온 기억에는 일치 항목이 없습니다. 이전 기억을 더 불러올 수 있습니다."
                            : "현재 필터에 맞는 기억이 없습니다."}
                      </p>
                    )}
                  </div>
                  {memoryError ? (
                    <p className="dashboard-inline-error" role="alert">
                      {memoryError}
                    </p>
                  ) : null}
                  {memoryHasMore &&
                  (memoryType !== "all" || selectedAgent.memory_has_more) ? (
                    <button
                      type="button"
                      className="dashboard-load-more"
                      disabled={memoryLoading}
                      onClick={() => void handleLoadOlderMemories()}
                    >
                      {memoryLoading ? "불러오는 중…" : "이전 기억 더 보기"}
                    </button>
                  ) : null}
                </section>
              ) : null}
              {tab === "plans" ? (
                <section className="dashboard-panel dashboard-list-panel">
                  <div className="dashboard-panel-title">
                    <span>
                      <ListTree size={14} /> 계획 계층
                    </span>
                    <strong>
                      재계획 이유 ·{" "}
                      {selectedAgent.last_replan_reason ?? "기록 없음"}
                    </strong>
                  </div>
                  <div className="dashboard-plan-stack">
                    <PlanCard
                      label="일일 계획"
                      item={selectedAgent.active_day}
                      currentTime={data?.world.current_time ?? null}
                    />
                    <PlanCard
                      label="시간 단위 계획"
                      item={selectedAgent.active_hourly}
                      currentTime={data?.world.current_time ?? null}
                    />
                    <PlanCard
                      label="분 단위 계획"
                      item={selectedAgent.active_minute}
                      currentTime={data?.world.current_time ?? null}
                    />
                  </div>
                  {planIssues.length ? (
                    <div className="dashboard-error" role="alert">
                      계획 시간 검증 · {planIssues.join(" · ")}
                    </div>
                  ) : (
                    <p className="dashboard-privacy-note">
                      일일 계획의 시간 공백·겹침이 없습니다.
                    </p>
                  )}
                  <div className="dashboard-day-plan">
                    {selectedAgent.day_plan.length ? (
                      selectedAgent.day_plan.map((item, index) => (
                        <PlanCard
                          key={`${item.start_time}-${index}`}
                          label={`일정 ${String(index + 1).padStart(2, "0")}`}
                          item={item}
                          currentTime={data?.world.current_time ?? null}
                        />
                      ))
                    ) : (
                      <p className="dashboard-empty-copy">
                        일일 계획이 아직 생성되지 않았습니다.
                      </p>
                    )}
                  </div>
                </section>
              ) : null}
              {tab === "reflection" ? (
                <section className="dashboard-panel dashboard-list-panel">
                  <div className="dashboard-panel-title">
                    <span>
                      <Sparkles size={14} /> 성찰
                    </span>
                    <strong>
                      {selectedAgent.reflection_status.accumulated_importance} /{" "}
                      {selectedAgent.reflection_status.threshold}
                    </strong>
                  </div>
                  <progress
                    className="dashboard-progress large"
                    max={Math.max(1, selectedAgent.reflection_status.threshold)}
                    value={
                      selectedAgent.reflection_status.accumulated_importance
                    }
                  />
                  <p>
                    다음 성찰까지{" "}
                    {Math.max(
                      0,
                      selectedAgent.reflection_status.threshold -
                        selectedAgent.reflection_status.accumulated_importance,
                    )}
                    점 · 전체 {selectedAgent.reflection_status.reflection_total}
                    개
                  </p>
                  <p className="dashboard-privacy-note">
                    마지막 성찰{" "}
                    {displayTime(
                      selectedAgent.reflection_status.last_reflection_at,
                    )}
                  </p>
                  <div className="dashboard-memory-list">
                    {reflectionMemories.length ? (
                      reflectionMemories.map((memory) => (
                        <MemoryRow
                          key={"reflection-" + memory.id}
                          memory={memory}
                        />
                      ))
                    ) : reflectionLoading ? (
                      <p className="dashboard-empty-copy">
                        성찰 목록을 불러오는 중입니다.
                      </p>
                    ) : (
                      <p className="dashboard-empty-copy">
                        {selectedAgent.reflection_status.reflection_total === 0
                          ? "아직 생성된 성찰이 없습니다. 임계치에 도달하면 생성됩니다."
                          : "저장된 성찰을 불러오지 못했습니다."}
                      </p>
                    )}
                  </div>
                  {reflectionError ? (
                    <p className="dashboard-inline-error" role="alert">
                      {reflectionError}
                    </p>
                  ) : null}
                  {reflectionHasMore ? (
                    <button
                      type="button"
                      className="dashboard-load-more"
                      disabled={reflectionLoading}
                      onClick={() => void handleLoadOlderReflections()}
                    >
                      {reflectionLoading ? "불러오는 중…" : "이전 성찰 더 보기"}
                    </button>
                  ) : null}
                </section>
              ) : null}
              {tab === "logs" ? (
                <section className="dashboard-panel dashboard-list-panel">
                  <div className="dashboard-panel-title">
                    <span>
                      <BrainCircuit size={14} /> 판단 진단
                    </span>
                  </div>
                  <div className="dashboard-toolbar">
                    <input
                      value={logQuery}
                      onChange={(event) => setLogQuery(event.target.value)}
                      placeholder="판단 로그 검색"
                      aria-label="판단 로그 검색"
                    />
                    <label>
                      <input
                        type="checkbox"
                        checked={logFailuresOnly}
                        onChange={(event) =>
                          setLogFailuresOnly(event.target.checked)
                        }
                      />
                      실패만
                    </label>
                  </div>
                  {data &&
                  data.oldest_sequence > 1 &&
                  (data.events[0]?.sequence ?? data.latest_sequence) >
                    data.oldest_sequence ? (
                    <p className="dashboard-privacy-note">
                      bounded buffer의 오래된 로그가 생략됐을 수 있습니다. 현재
                      제공 범위 {data.oldest_sequence}–{data.latest_sequence}
                    </p>
                  ) : null}
                  <div className="dashboard-timeline">
                    {selectedAgentEvents.length ? (
                      selectedAgentEvents.map((event) => (
                        <EventRow key={event.sequence} event={event} />
                      ))
                    ) : (
                      <p className="dashboard-empty-copy">
                        선택한 조건에 맞는 판단 로그가 없습니다.
                      </p>
                    )}
                  </div>
                </section>
              ) : null}
            </div>
          )}
        </section>

        <aside className="dashboard-timeline-panel">
          <header>
            <div>
              <Footprints size={14} />
              <strong>실시간 로그</strong>
            </div>
            <span>{data?.latest_sequence ?? 0} EVENTS</span>
          </header>
          <div className="dashboard-log-filter">
            <MessageCircle size={13} />
            <select
              value={eventAgentFilter}
              onChange={(event) => setEventAgentFilter(event.target.value)}
              aria-label="로그 에이전트 필터"
            >
              <option value="all">모든 에이전트</option>
              {(data?.agents ?? []).map((agent) => (
                <option value={agent.agent_id} key={agent.agent_id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </div>
          <div className="dashboard-timeline">
            {railEvents.length ? (
              railEvents.map((event) => (
                <EventRow key={event.sequence} event={event} />
              ))
            ) : (
              <div className="dashboard-empty-log">
                <BrainCircuit size={20} />
                <p>아직 완료된 인지 판단 로그가 없습니다.</p>
                <small>
                  에이전트가 대화를 시작하면 실제 로그가 이곳에 쌓입니다.
                </small>
              </div>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
