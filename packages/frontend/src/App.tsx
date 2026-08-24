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
      liveAgents[id] ?? {
        agent_id: id,
        name: spawn.name,
        tile_position: { x: spawn.x / 32, y: spawn.y / 32 },
        position: { x: spawn.x, y: spawn.y },
        destination: null,
        current_action: "waiting_for_world",
        plan: "Connecting to the autonomous world…",
        route_remaining: 0,
      }
    );
  });

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
          <strong>09:42</strong>
          <span>SPRING 8</span>
        </div>
        <div className={`connection-chip ${connectionStatus}`}>
          <Radio size={13} />{" "}
          {connectionStatus === "live"
            ? `WORLD TICK ${revision}`
            : connectionStatus.toUpperCase()}
        </div>
      </header>

      <button
        className="inspector-toggle"
        onClick={() => setInspectorOpen((open) => !open)}
        aria-label="Toggle resident inspector"
      >
        {inspectorOpen ? <X size={18} /> : <Users size={18} />}
      </button>

      <aside className={`game-inspector ${inspectorOpen ? "open" : ""}`}>
        <div className="inspector-title">
          <div>
            <span className="pixel-kicker">
              <Eye size={12} /> LIVE RESIDENTS
            </span>
            <h2>마을 관찰자</h2>
          </div>
          <span className="resident-count">{displayedAgents.length}</span>
        </div>

        <div className="resident-list">
          {displayedAgents.map((agent, index) => (
            <article className="resident-card" key={agent.agent_id}>
              <div className={`pixel-portrait portrait-${index % 2}`}>
                <span />
              </div>
              <div className="resident-copy">
                <div className="resident-name">
                  <strong>{agent.name}</strong>
                  <i>
                    {agent.current_action.includes("moving")
                      ? "WALKING"
                      : "ACTIVE"}
                  </i>
                </div>
                <p>{agent.plan.split("|")[0]}</p>
                <div className="destination">
                  <MapPin size={11} />{" "}
                  {agent.destination?.split(" > ").at(-1) ?? "Town Square"}
                </div>
              </div>
              <ChevronRight size={16} className="card-chevron" />
            </article>
          ))}
        </div>

        <section className="seed-event">
          <span className="pixel-kicker">TODAY'S SEED EVENT</span>
          <h3>Moonflower picnic</h3>
          <p>
            광장 게시판에서 시작된 소식이 주민들의 기억과 계획을 어떻게 바꾸는지
            관찰합니다.
          </p>
          <div className="event-progress">
            <span />
          </div>
          <small>INFORMATION SPREAD · 1 / 2</small>
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
