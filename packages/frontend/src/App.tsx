import { useEffect, useRef, useState } from "react";
import {
  ChevronRight,
  Clock3,
  Eye,
  MapPin,
  Radio,
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

const mapSpawns = getLayer("spawns");

function App() {
  const gameContainerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const connectionStatus = useGameStore((state) => state.connectionStatus);
  const liveAgents = useGameStore((state) => state.agents);
  const revision = useGameStore((state) => state.revision);
  const currentTime = useGameStore((state) => state.currentTime);
  const schedulerRunning = useGameStore((state) => state.schedulerRunning);
  const selectedAgentId = useGameStore((state) => state.selectedAgentId);
  const selectAgent = useGameStore((state) => state.selectAgent);
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
      liveAgents[id] ?? liveAgents[id.toLocaleLowerCase()] ?? {
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
      }
    );
  });

  function handleResidentSelect(agentId: string): void {
    selectAgent(agentId);
    if (window.matchMedia("(max-width: 720px)").matches) {
      setInspectorOpen(false);
    }
  }

  return (
    <main className="game-shell">
      <div ref={gameContainerRef} className="game-viewport" />

      <header className="game-hud top-hud">
        <div className="game-brand">
          <span className="pixel-leaf">✦</span>
          <div>
            <strong>AGENT CROSSING</strong>
            <small>{getMapProperty("name", "Briar Cove")}</small>
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
          <span>{currentTime ? new Date(currentTime).toLocaleDateString("ko-KR") : "DAY --"}</span>
        </div>
        <div className={`connection-chip ${connectionStatus}`}>
          <Radio size={13} />{" "}
          {connectionStatus === "live"
            ? `${schedulerRunning ? "하루 진행 중" : "일시 정지"} · 틱 ${revision}`
            : connectionStatus === "connecting"
              ? "연결 중"
              : "오프라인"}
        </div>
      </header>

      <button
        className="inspector-toggle"
        onClick={() => setInspectorOpen((open) => !open)}
        aria-label="주민 관찰 패널 열기 또는 닫기"
      >
        {inspectorOpen ? <X size={18} /> : <Users size={18} />}
      </button>

      <aside className={`game-inspector ${inspectorOpen ? "open" : ""}`}>
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
                    {agent.current_action.includes("moving")
                      ? "이동 중"
                      : "활동 중"}
                  </i>
                </div>
                <p>{agent.active_minute?.action_content ?? agent.plan.split("|")[0]}</p>
                <div className="destination">
                  <MapPin size={11} />{" "}
                  {agent.destination?.split(" > ").at(-1) ?? "마을 광장"}
                </div>
              </div>
              <ChevronRight size={16} className="card-chevron" />
            </button>
          ))}
        </div>

        <section className="seed-event">
          <span className="pixel-kicker">오늘의 씨앗 사건</span>
          <h3>달맞이꽃 소풍</h3>
          <p>
            광장 게시판에서 시작된 소식이 주민들의 기억과 계획을 어떻게 바꾸는지
            관찰합니다.
          </p>
          <div className="event-progress">
            <span />
          </div>
          <small>정보 확산 · 1 / 2</small>
        </section>
      </aside>

      <footer className="control-hint">
        <kbd>DRAG</kbd> 카메라 이동 <span /> <kbd>WHEEL</kbd> 확대·축소 <span />{" "}
        <kbd>CLICK NPC</kbd> 따라가기
      </footer>
    </main>
  );
}

export default App;
