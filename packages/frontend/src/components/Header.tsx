import { useWorldStore } from "../stores";
import { isNightHour, simHourOf } from "../game/daylight";
import {
  CONNECTION_DOT_CLASSES,
  CONNECTION_LABELS,
  CONNECTION_SHORT_LABELS,
  formatSimClock,
  formatSimTime,
} from "./format";

export function Header() {
  const snapshot = useWorldStore((state) => state.snapshot);
  const connection = useWorldStore((state) => state.connection);
  const debug = useWorldStore((state) => state.debug);
  const toggleDebug = useWorldStore((state) => state.toggleDebug);

  const hour = snapshot ? simHourOf(snapshot.sim_time) : null;
  return (
    <header className="flex items-center justify-between gap-2 border-b border-amber-900/30 bg-amber-50 px-3 py-2 text-stone-800 md:gap-4 md:px-4">
      <h1 className="whitespace-nowrap text-base font-bold text-emerald-700 md:text-lg">Agent Crossing</h1>
      <div className="flex items-center gap-2 whitespace-nowrap text-sm md:gap-4">
        <span data-testid="sim-time">
          {hour === null ? null : <span aria-hidden="true">{isNightHour(hour) ? "🌙 " : "☀️ "}</span>}
          <span className="md:hidden">{snapshot ? formatSimClock(snapshot.sim_time) : "--"}</span>
          <span className="hidden md:inline">{snapshot ? formatSimTime(snapshot.sim_time) : "--"}</span>
        </span>
        <span className="hidden md:inline" data-testid="tick">
          tick {snapshot ? snapshot.tick : "-"}
        </span>
        <span className="flex items-center gap-1" data-testid="connection">
          <span className={`inline-block h-2 w-2 rounded-full ${CONNECTION_DOT_CLASSES[connection]}`} />
          <span className="md:hidden">{CONNECTION_SHORT_LABELS[connection]}</span>
          <span className="hidden md:inline">{CONNECTION_LABELS[connection]}</span>
        </span>
        <button
          type="button"
          onClick={toggleDebug}
          aria-pressed={debug}
          className={`min-h-11 rounded px-2 py-1 text-xs font-semibold md:min-h-0 ${
            debug ? "bg-pink-500 text-white" : "bg-stone-200 text-stone-700 hover:bg-stone-300"
          }`}
        >
          디버그 {debug ? "ON" : "OFF"}
        </button>
      </div>
    </header>
  );
}
