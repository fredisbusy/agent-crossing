import { useEffect, useRef, useState } from "react";
import {
  ChevronRight,
  Clock3,
  Eye,
  MapPin,
  Radio,
  BrainCircuit,
  Users,
  X,
} from "lucide-react";
import Phaser from "phaser";
import { GridEngine } from "grid-engine";
import { InteriorScene } from "./game/InteriorScene";
import { MainScene } from "./game/MainScene";
import { useWorldStream } from "./hooks/useWorldStream";
import { getLayer, getMapProperty, getProperty } from "./map/tiled";
import { useGameStore } from "./stores/game.store";
import {
  buildMainEventView,
  residentDestinationLabel,
  residentPlanLabel,
  residentStatusLabel,
} from "./ui/observer";
import { SessionMenu } from "./components/SessionMenu";

const mapSpawns = getLayer("spawns");

function GameTextOverlay() {
  const labels = useGameStore((state) => state.gameTextOverlay.labels);

  return (
    <div className="game-text-overlay" aria-hidden="true">
      {labels.map((label) => (
        <span
          className={`game-map-text tone-${label.tone} anchor-${label.anchor}${
            label.selected ? " selected" : ""
          }`}
          key={label.id}
          style={{
            left: label.left,
            top: label.top,
            maxWidth: label.maxWidth,
          }}
        >
          {label.text}
        </span>
      ))}
    </div>
  );
}

function App() {
  const gameContainerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const connectionStatus = useGameStore((state) => state.connectionStatus);
  const liveAgents = useGameStore((state) => state.agents);
  const revision = useGameStore((state) => state.revision);
  const currentTime = useGameStore((state) => state.currentTime);
  const schedulerRunning = useGameStore((state) => state.schedulerRunning);
  const planningError = useGameStore((state) => state.planningError);
  const selectedAgentId = useGameStore((state) => state.selectedAgentId);
  const selectAgent = useGameStore((state) => state.selectAgent);
  const sceneContext = useGameStore((state) => state.sceneContext);
  const interactionNotice = useGameStore((state) => state.interactionNotice);
  const dismissInteractionNotice = useGameStore(
    (state) => state.dismissInteractionNotice,
  );
  useWorldStream();

  useEffect(() => {
    if (gameContainerRef.current && !gameRef.current) {
      gameRef.current = new Phaser.Game({
        type: Phaser.AUTO,
        parent: gameContainerRef.current,
        width: 1280,
        height: 800,
        backgroundColor: "#173b2b",
        physics: { default: "arcade" },
        scale: {
          mode: Phaser.Scale.RESIZE,
          autoCenter: Phaser.Scale.CENTER_BOTH,
        },
        render: { antialias: false, pixelArt: true, roundPixels: true },
        plugins: {
          scene: [
            {
              key: "gridEngine",
              plugin: GridEngine,
              mapping: "gridEngine",
            },
          ],
        },
        scene: [MainScene, InteriorScene],
      });
    }
    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []);

  const displayedAgents = mapSpawns.map((spawn) => {
    const id = getProperty(spawn, "agent_id", spawn.name);
    return (
      liveAgents[id] ??
      liveAgents[id.toLocaleLowerCase()] ?? {
        agent_id: id,
        name: spawn.name,
        tile_position: { x: spawn.x / 32, y: spawn.y / 32 },
        position: { x: spawn.x, y: spawn.y },
        destination: null,
        current_action: "세계를 기다리는 중",
        plan: "자율 세계에 연결하는 중…",
        route_remaining: 0,
        active_day: null,
        active_hourly: null,
        active_minute: null,
        day_plan: [],
        bubble_kind: "action",
        bubble_text: "자율 세계에 연결하는 중…",
      }
    );
  });
  const selectedAgent =
    displayedAgents.find(
      (agent) =>
        agent.agent_id.toLocaleLowerCase() ===
        selectedAgentId.toLocaleLowerCase(),
    ) ?? displayedAgents[0];
  const mainEvent = planningError
    ? {
        title: "일정 생성 오류",
        description: planningError,
        progressPercent: 0,
        progressLabel: "계획 생성이 중단되었습니다",
      }
    : buildMainEventView(selectedAgent, currentTime);

  function handleResidentSelect(agentId: string): void {
    selectAgent(agentId);
    if (window.matchMedia("(max-width: 720px)").matches) {
      setInspectorOpen(false);
    }
  }

  return (
    <main className="game-shell">
      <div ref={gameContainerRef} className="game-viewport" />
      <GameTextOverlay />

      <header className="game-hud top-hud">
        <div className="game-brand">
          <span className="pixel-leaf">✦</span>
          <div>
            <strong>AGENT CROSSING</strong>
            <small>{getMapProperty("name", "브라이어 코브")}</small>
          </div>
        </div>
        <div className="clock-chip">
          <Clock3 size={14} />
          <strong>
            {currentTime
              ? new Intl.DateTimeFormat("ko-KR", {
                  hour: "2-digit",
                  minute: "2-digit",
                  hour12: false,
                }).format(new Date(currentTime))
              : "--:--"}
          </strong>
          <span>
            {currentTime
              ? new Date(currentTime).toLocaleDateString("ko-KR")
              : "DAY --"}
          </span>
        </div>
        <div
          className={`connection-chip ${planningError ? "offline" : connectionStatus}`}
        >
          <Radio size={13} />{" "}
          {planningError
            ? "일정 오류"
            : connectionStatus === "live"
              ? `${schedulerRunning ? "하루 진행 중" : "일시 정지"} · 틱 ${revision}`
              : connectionStatus === "connecting"
                ? "연결 중"
                : "오프라인"}
        </div>
        <a className="dashboard-link" href="/dashboard">
          <BrainCircuit size={13} /> DASHBOARD
        </a>
        <SessionMenu />
      </header>

      <button
        className="inspector-toggle"
        onClick={() => setInspectorOpen((open) => !open)}
        aria-label="주민 관찰 패널 열기 또는 닫기"
      >
        {inspectorOpen ? <X size={18} /> : <Users size={18} />}
      </button>

      <aside
        className={`game-inspector ${inspectorOpen ? "open" : ""}`}
        aria-hidden={!inspectorOpen}
        inert={inspectorOpen ? undefined : true}
      >
        <div className="inspector-title">
          <div>
            <span className="pixel-kicker">
              <Eye size={12} /> 실시간 주민
            </span>
            <h2>마을 관찰자</h2>
          </div>
          <span className="resident-count">{displayedAgents.length}</span>
        </div>

        <div className="resident-list">
          {displayedAgents.map((agent, index) => (
            <button
              type="button"
              className={`resident-card ${
                selectedAgentId.toLocaleLowerCase() ===
                agent.agent_id.toLocaleLowerCase()
                  ? "selected"
                  : ""
              }`}
              key={agent.agent_id}
              onClick={() => handleResidentSelect(agent.agent_id)}
              aria-label={`${agent.name} 따라가기`}
              aria-pressed={
                selectedAgentId.toLocaleLowerCase() ===
                agent.agent_id.toLocaleLowerCase()
              }
            >
              <div className={`pixel-portrait portrait-${index % 2}`}>
                <span />
              </div>
              <div className="resident-copy">
                <div className="resident-name">
                  <strong>{agent.name}</strong>
                  <i>
                    {residentStatusLabel(
                      agent.current_action,
                      connectionStatus,
                    )}
                  </i>
                </div>
                <p>
                  {planningError ? "일정 생성 실패" : residentPlanLabel(agent)}
                </p>
                <div className="destination">
                  <MapPin size={11} />{" "}
                  {residentDestinationLabel(agent, connectionStatus)}
                </div>
              </div>
              <ChevronRight size={16} className="card-chevron" />
            </button>
          ))}
        </div>

        <section className="seed-event">
          <span className="pixel-kicker">오늘의 메인이벤트</span>
          <h3>{mainEvent.title}</h3>
          <p>{mainEvent.description}</p>
          <div className="event-progress">
            <span style={{ width: `${mainEvent.progressPercent}%` }} />
          </div>
          <small>{mainEvent.progressLabel}</small>
        </section>
      </aside>

      {interactionNotice ? (
        <section className="interaction-notice" role="status">
          <div>
            <strong>{interactionNotice.title}</strong>
            <p>{interactionNotice.description}</p>
          </div>
          <button
            type="button"
            onClick={dismissInteractionNotice}
            aria-label="상호작용 안내 닫기"
          >
            <X size={14} />
          </button>
        </section>
      ) : null}

      <footer className="control-hint">
        {sceneContext.kind === "world" ? (
          <>
            <span className="desktop-control-hint">
              <kbd>DRAG</kbd> 카메라 이동 <i /> <kbd>WHEEL</kbd> 확대·축소 <i />
              <kbd>CLICK NPC</kbd> 따라가기
            </span>
            <span className="mobile-control-hint">
              <kbd>DRAG</kbd> 카메라 이동 <i /> <kbd>PINCH</kbd> 확대·축소 <i />
              <kbd>TAP NPC</kbd> 따라가기
            </span>
          </>
        ) : (
          <>
            <span className="desktop-control-hint">
              <kbd>CLICK NPC</kbd> 따라가기 <i /> <kbd>ESC / E</kbd> 나가기
            </span>
            <span className="mobile-control-hint">
              <kbd>TAP NPC</kbd> 따라가기 <i /> <kbd>TAP EXIT</kbd> 나가기
            </span>
          </>
        )}
      </footer>
    </main>
  );
}

export default App;
