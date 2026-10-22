import Phaser from "phaser";
import type { ResidentSnapshot } from "@agent-crossing/shared";
import { DEFAULT_TICK_INTERVAL_MS } from "../../net";
import { useWorldStore } from "../../stores";
import { DaylightLayer } from "../daylight";
import { buildTownMap, LocationOverlay, preloadTownMap } from "../map";
import { BubbleTracker, MotionTracker, ResidentView, SpotMap } from "../residents";
import { attachCameraControls } from "./camera-controls";

export const TOWN_SCENE_KEY = "TownScene";

export interface SceneCameraState {
  scroll_x: number;
  scroll_y: number;
  zoom: number;
}

/** 백엔드 스냅샷을 보간해 그리기만 하는 마을 장면 (SPEC §15). */
export class TownScene extends Phaser.Scene {
  private clockMs = 0;
  private manualClock = false;
  private readonly motion = new MotionTracker();
  private readonly bubbles = new BubbleTracker();
  private readonly views = new Map<string, ResidentView>();
  private residents: readonly ResidentSnapshot[] = [];
  private overlay: LocationOverlay | null = null;
  private daylight: DaylightLayer | null = null;
  private spots = new SpotMap([], []);
  private unsubscribe: (() => void) | null = null;

  constructor() {
    super(TOWN_SCENE_KEY);
  }

  preload(): void {
    preloadTownMap(this);
  }

  create(): void {
    this.cameras.main.setBackgroundColor("#5a8f5e");
    const town = buildTownMap(this);
    this.overlay = new LocationOverlay(this, town.areas);
    this.daylight = new DaylightLayer(this, town);
    this.spots = new SpotMap(town.furniture, town.decor);
    attachCameraControls(this, town.widthPx, town.heightPx);

    const initial = useWorldStore.getState();
    this.overlay.setVisible(initial.debug);
    if (initial.snapshot) this.applyResidents(initial.snapshot.residents);
    if (initial.snapshot) this.daylight.setSimTime(initial.snapshot.sim_time);

    this.unsubscribe = useWorldStore.subscribe((state, previous) => {
      if (state.snapshot !== previous.snapshot && state.snapshot) {
        this.applyResidents(state.snapshot.residents);
        this.daylight?.setSimTime(state.snapshot.sim_time);
      }
      if (state.debug !== previous.debug) this.overlay?.setVisible(state.debug);
    });
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.unsubscribe?.());
  }

  update(_time: number, delta: number): void {
    if (!this.manualClock) this.clockMs += delta;
    this.syncViews();
  }

  /** QA: 실시간 시계를 멈추고 이후엔 `advanceClock`으로만 흐르게 한다. */
  useManualClock(): void {
    this.manualClock = true;
  }

  advanceClock(ms: number): void {
    this.clockMs += ms;
  }

  getCameraState(): SceneCameraState {
    const camera = this.cameras.main;
    return { scroll_x: Math.round(camera.scrollX), scroll_y: Math.round(camera.scrollY), zoom: camera.zoom };
  }

  getBubbleText(id: string): string | null {
    return this.bubbles.textAt(id, this.clockMs);
  }

  private applyResidents(residents: readonly ResidentSnapshot[]): void {
    this.residents = residents;
    this.motion.observe(residents, this.clockMs, DEFAULT_TICK_INTERVAL_MS);
    this.bubbles.observe(residents, this.clockMs);
    const alive = new Set(residents.map((resident) => resident.resident_id));
    for (const [id, view] of this.views) {
      if (!alive.has(id)) {
        view.destroy();
        this.views.delete(id);
      }
    }
    for (const resident of residents) {
      if (!this.views.has(resident.resident_id)) {
        const view = new ResidentView(this, resident, (id) => useWorldStore.getState().selectResident(id), this.spots);
        this.views.set(resident.resident_id, view);
      }
    }
    this.syncViews();
  }

  private syncViews(): void {
    const selected = useWorldStore.getState().selectedResidentId;
    for (const resident of this.residents) {
      const view = this.views.get(resident.resident_id);
      const position = this.motion.positionAt(resident.resident_id, this.clockMs);
      if (!view || !position) continue;
      view.placeAtTile(position.x, position.y);
      view.update(resident, this.bubbles.textAt(resident.resident_id, this.clockMs), resident.resident_id === selected);
    }
  }
}
