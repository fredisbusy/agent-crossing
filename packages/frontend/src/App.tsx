import { useEffect, useRef } from "react";
import { Clock3, Map, MessageCircle, Sparkles, Users } from "lucide-react";
import Phaser from "phaser";
import { MainScene } from "./game/MainScene";
import { getLayer, getMapProperty, getProperty } from "./map/tiled";

const agents = getLayer("spawns");
const locations = getLayer("locations");

function App() {
  const gameContainerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    if (gameContainerRef.current && !gameRef.current) {
      const config: Phaser.Types.Core.GameConfig = {
        type: Phaser.AUTO,
        parent: gameContainerRef.current,
        width: 1100,
        height: 720,
        backgroundColor: "#a9cf91",
        physics: { default: "arcade" },
        scale: {
          mode: Phaser.Scale.RESIZE,
          autoCenter: Phaser.Scale.CENTER_BOTH,
        },
        render: { antialias: true, roundPixels: true },
        scene: [MainScene],
      };

      gameRef.current = new Phaser.Game(config);
    }

    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Sparkles size={19} />
          </div>
          <div>
            <p className="eyebrow">AUTONOMOUS SOCIAL WORLD</p>
            <h1>Agent Crossing</h1>
          </div>
        </div>
        <div className="world-status">
          <span className="status-dot" />
          <span>Briar Cove is awake</span>
          <span className="divider" />
          <Clock3 size={15} />
          <strong>09:42 AM</strong>
        </div>
      </header>

      <section className="workspace">
        <div className="world-panel">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">
                <Map size={14} /> LIVE WORLD
              </span>
              <h2>{getMapProperty("name", "Briar Cove")}</h2>
            </div>
            <div className="world-metrics">
              <span>
                <Users size={14} /> {agents.length} residents
              </span>
              <span>{locations.length} places</span>
            </div>
          </div>
          <div ref={gameContainerRef} className="game-canvas" />
          <div className="map-legend">
            <span>
              <i className="legend-swatch agent" /> autonomous agent
            </span>
            <span>
              <i className="legend-swatch social" /> social space
            </span>
            <span>
              <i className="legend-swatch nature" /> restorative space
            </span>
            <span className="map-note">
              Tiled semantic map · backend-authoritative navigation
            </span>
          </div>
        </div>

        <aside className="inspector">
          <div className="inspector-heading">
            <span className="section-kicker">
              <Users size={14} /> RESIDENTS
            </span>
            <span className="live-pill">LIVE</span>
          </div>

          <div className="agent-list">
            {agents.map((agent, index) => (
              <article
                className={`agent-card ${index === 0 ? "selected" : ""}`}
                key={agent.id}
              >
                <div
                  className="agent-avatar"
                  style={{
                    backgroundColor: getProperty(agent, "color", "#6b8fd6"),
                  }}
                >
                  {agent.name.slice(0, 1)}
                  <span className="online-dot" />
                </div>
                <div className="agent-copy">
                  <div className="agent-title">
                    <strong>{agent.name}</strong>
                    <span>{index === 0 ? "☕" : "📚"}</span>
                  </div>
                  <p>
                    {index === 0
                      ? "Heading to the café"
                      : "Reviewing morning plans"}
                  </p>
                </div>
              </article>
            ))}
          </div>

          <section className="activity-card">
            <div className="activity-title">
              <MessageCircle size={16} />
              <strong>World pulse</strong>
            </div>
            <div className="timeline-item">
              <span className="timeline-dot coral" />
              <div>
                <strong>Sujin</strong> noticed the new community post.
                <time>2 min ago</time>
              </div>
            </div>
            <div className="timeline-item">
              <span className="timeline-dot blue" />
              <div>
                <strong>Jiho</strong> updated the morning plan.
                <time>5 min ago</time>
              </div>
            </div>
          </section>

          <section className="experiment-card">
            <span className="section-kicker">TODAY'S SEED EVENT</span>
            <h3>Moonflower picnic</h3>
            <p>
              Observe whether the invitation spreads from the town board to both
              residents.
            </p>
            <div className="progress-track">
              <span />
            </div>
            <div className="progress-label">
              <span>Information spread</span>
              <strong>1 / 2</strong>
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

export default App;
