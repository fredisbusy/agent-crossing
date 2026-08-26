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
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useDashboardState } from "../hooks/useDashboardState";
import "./dashboard.css";

type DashboardTab =
  | "overview"
  | "relationship"
  | "memory"
  | "plans"
  | "reflection"
  | "logs";

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
  if (action.startsWith("arrived_at:")) return `${action.slice(11)}에 도착`;
  if (action.startsWith("at:")) return `${action.slice(3)}에 머무는 중`;
  if (action === "planning_route") return "이동 경로 계산 중";
  return action ? "상태 확인 중" : "상태 없음";
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
}: {
  label: string;
  item: PlanItemState | null;
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
      {memory.citations?.length ? (
        <small>근거 기억 #{memory.citations.join(", #")}</small>
      ) : null}
    </article>
  );
}

function EventRow({ event }: { event: DashboardEvent }) {
  const primary =
    event.reply ||
    event.thought ||
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
          {event.thought ? <span>생각</span> : null}
          {event.self_critique ? <span>자기비평</span> : null}
          {event.parse_failure ? (
            <span className="error">파싱 실패</span>
          ) : null}
          {event.silent_reason ? (
            <span>침묵 · {event.silent_reason}</span>
          ) : null}
        </div>
        <details>
          <summary>전체 판단 로그 보기</summary>
          <dl>
            <dt>모델 생각</dt>
            <dd>{event.model_thought || "기록 없음"}</dd>
            <dt>자기 비평</dt>
            <dd>{event.self_critique || "기록 없음"}</dd>
            <dt>결정 이유</dt>
            <dd>{event.decision_reason || "기록 없음"}</dd>
            <dt>행동 요약</dt>
            <dd>{event.action_summary || "기록 없음"}</dd>
          </dl>
          <div className="dashboard-json-grid">
            <div>
              <span>DECISION PROCESS</span>
              <pre>{JSON.stringify(event.decision_process, null, 2)}</pre>
            </div>
            <div>
              <span>GOVERNANCE TRACE</span>
              <pre>{JSON.stringify(event.governance_trace, null, 2)}</pre>
            </div>
          </div>
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
  initialTargetId,
}: {
  agent: DashboardAgent;
  agents: DashboardAgent[];
  onSelect: (agentId: string, targetId: string) => void;
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
        대화와 확정된 상호작용이 친숙도·신뢰·인간적 호감·긴장을 바꿉니다. 이성적
        관심은 명시적인 애정 사건에서만 변합니다. 수치는 {agent.name}의
        관점에서만 적용됩니다.
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
              onClick={() => setTargetId(item.target_agent_id)}
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
              <details>
                <summary>
                  관계를 뒷받침하는 기록 · 총 {relationship.evidence_total}개
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
                    최근 {relationship.evidence.length}개만 표시합니다.
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
  return (
    <div className="dashboard-overview-grid">
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
            <dd>{agent.current_location_path ?? "확인할 수 없음"}</dd>
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
            <BrainCircuit size={14} /> 최근 생각
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
          {agent.active_minute?.action_content ??
            agent.current_plan_context[0] ??
            "계획 없음"}
        </h3>
        <p>
          {agent.active_minute?.location ?? agent.destination ?? "장소 미정"}
        </p>
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
        <div className="dashboard-progress">
          <span
            style={{
              width: `${Math.min(100, (agent.reflection_status.accumulated_importance / Math.max(1, agent.reflection_status.threshold)) * 100)}%`,
            }}
          />
        </div>
        <p>임계치에 도달하면 최근 기억을 바탕으로 고차원 성찰을 생성합니다.</p>
      </section>
    </div>
  );
}

export function Dashboard() {
  const { data, connection, error } = useDashboardState();
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [tab, setTab] = useState<DashboardTab>("overview");
  const [eventAgentFilter, setEventAgentFilter] = useState<string>("all");
  const [relationshipTargetId, setRelationshipTargetId] = useState<string>("");

  useEffect(() => {
    document.body.classList.add("dashboard-route");
    return () => document.body.classList.remove("dashboard-route");
  }, []);

  useEffect(() => {
    if (!selectedAgentId && data?.agents[0]) {
      setSelectedAgentId(data.agents[0].agent_id);
    }
  }, [data, selectedAgentId]);

  const selectedAgent =
    data?.agents.find((agent) => agent.agent_id === selectedAgentId) ??
    data?.agents[0] ??
    null;
  const filteredEvents = useMemo(() => {
    const events = data?.events ?? [];
    return events
      .filter(
        (event) =>
          eventAgentFilter === "all" || event.agent_id === eventAgentFilter,
      )
      .slice()
      .reverse();
  }, [data?.events, eventAgentFilter]);

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
          className={`dashboard-connection ${data?.world.planning_error ? "offline" : connection}`}
        >
          <Radio size={14} />
          {data?.world.planning_error
            ? "PLANNING ERROR"
            : connection === "live"
              ? "LIVE"
              : connection === "connecting"
                ? "CONNECTING"
                : "OFFLINE"}
        </div>
      </header>

      {error ? (
        <div className="dashboard-error">
          {error} · 실제 runtime 연결을 다시 시도하고 있습니다.
        </div>
      ) : null}
      {data?.world.planning_error ? (
        <div className="dashboard-error">
          일정 생성 오류 · {data.world.planning_error}
        </div>
      ) : null}

      <div className="dashboard-layout">
        <aside className="dashboard-agent-rail">
          <div className="dashboard-rail-title">
            <Eye size={14} />
            <span>에이전트</span>
            <b>{data?.agents.length ?? 0}</b>
          </div>
          <div className="dashboard-agent-list">
            {(data?.agents ?? []).map((agent, index) => (
              <button
                type="button"
                key={agent.agent_id}
                className={
                  agent.agent_id === selectedAgent?.agent_id ? "selected" : ""
                }
                onClick={() => {
                  setSelectedAgentId(agent.agent_id);
                  setRelationshipTargetId("");
                }}
              >
                <span className={`dashboard-avatar avatar-${index % 2}`}>
                  {agent.name.slice(0, 1)}
                </span>
                <div>
                  <strong>{agent.name}</strong>
                  <small>{actionLabel(agent.current_action)}</small>
                </div>
                <ChevronRight size={15} />
              </button>
            ))}
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
          <nav className="dashboard-tabs" aria-label="에이전트 상세 정보">
            {tabs.map((item) => (
              <button
                type="button"
                key={item.id}
                className={tab === item.id ? "active" : ""}
                onClick={() => setTab(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {!selectedAgent ? (
            <section className="dashboard-empty">
              <RefreshCw size={24} />
              <h2>에이전트 runtime을 기다리는 중</h2>
              <p>실제 인지 runtime이 준비되면 이 화면에 표시됩니다.</p>
            </section>
          ) : (
            <div className="dashboard-tab-content">
              <div className="dashboard-agent-heading">
                <div>
                  <span>{selectedAgent.agent_id}</span>
                  <h1>{selectedAgent.name}</h1>
                </div>
                <p>{selectedAgent.bubble_text || "현재 관찰 문장 없음"}</p>
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
                />
              ) : null}
              {tab === "memory" ? (
                <section className="dashboard-panel dashboard-list-panel">
                  <div className="dashboard-panel-title">
                    <span>
                      <Database size={14} /> Memory Stream
                    </span>
                    <strong>{selectedAgent.memories.length}</strong>
                  </div>
                  <div className="dashboard-memory-list">
                    {selectedAgent.memories.length ? (
                      selectedAgent.memories.map((memory) => (
                        <MemoryRow
                          key={`${memory.node_type}-${memory.id}`}
                          memory={memory}
                        />
                      ))
                    ) : (
                      <p className="dashboard-empty-copy">
                        저장된 기억이 없습니다.
                      </p>
                    )}
                  </div>
                </section>
              ) : null}
              {tab === "plans" ? (
                <section className="dashboard-panel dashboard-list-panel">
                  <div className="dashboard-panel-title">
                    <span>
                      <ListTree size={14} /> Plan hierarchy
                    </span>
                  </div>
                  <div className="dashboard-plan-stack">
                    <PlanCard label="DAY" item={selectedAgent.active_day} />
                    <PlanCard label="HOUR" item={selectedAgent.active_hourly} />
                    <PlanCard
                      label="MINUTE"
                      item={selectedAgent.active_minute}
                    />
                  </div>
                  <div className="dashboard-day-plan">
                    {selectedAgent.day_plan.map((item, index) => (
                      <PlanCard
                        key={`${item.start_time}-${index}`}
                        label={`DAY ${String(index + 1).padStart(2, "0")}`}
                        item={item}
                      />
                    ))}
                  </div>
                </section>
              ) : null}
              {tab === "reflection" ? (
                <section className="dashboard-panel dashboard-list-panel">
                  <div className="dashboard-panel-title">
                    <span>
                      <Sparkles size={14} /> Reflection
                    </span>
                    <strong>
                      {selectedAgent.reflection_status.accumulated_importance} /{" "}
                      {selectedAgent.reflection_status.threshold}
                    </strong>
                  </div>
                  <div className="dashboard-progress large">
                    <span
                      style={{
                        width: `${Math.min(100, (selectedAgent.reflection_status.accumulated_importance / Math.max(1, selectedAgent.reflection_status.threshold)) * 100)}%`,
                      }}
                    />
                  </div>
                  <div className="dashboard-memory-list">
                    {selectedAgent.memories
                      .filter((memory) => memory.node_type === "REFLECTION")
                      .map((memory) => (
                        <MemoryRow
                          key={`reflection-${memory.id}`}
                          memory={memory}
                        />
                      ))}
                  </div>
                </section>
              ) : null}
              {tab === "logs" ? (
                <section className="dashboard-panel dashboard-list-panel">
                  <div className="dashboard-panel-title">
                    <span>
                      <BrainCircuit size={14} /> Decision diagnostics
                    </span>
                  </div>
                  <div className="dashboard-timeline">
                    {filteredEvents
                      .filter(
                        (event) => event.agent_id === selectedAgent.agent_id,
                      )
                      .map((event) => (
                        <EventRow key={event.sequence} event={event} />
                      ))}
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
            {filteredEvents.length ? (
              filteredEvents.map((event) => (
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
