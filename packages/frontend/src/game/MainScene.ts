import Phaser from "phaser";
import type { SpatialAgentState } from "@agent-crossing/shared";
import { GridEngine, NumberOfDirections } from "grid-engine";
import {
  getLayer,
  getProperty,
  parseColor,
  townMap,
  type TiledObject,
} from "../map/tiled";
import { useGameStore } from "../stores/game.store";
import {
  createIndoorResidentView,
  drawDollhouseHome,
  type DollhouseHomeView,
  type IndoorResidentView,
} from "./DollhouseHome";
import {
  drawDollhouseBuilding,
  type DollhouseBuildingView,
} from "./DollhouseBuilding";
import { createPixelTextures, TILE, TILE_SIZE } from "./pixelTextures";
import { ServerGridMovement } from "./gridMovement";
import { agentBubbleLabel } from "./agentBubble";
import { GameTextOverlayController } from "./gameText";
import {
  HOME_ROOMS,
  isAgentAtLocation,
  isAgentInsideHome,
  resolveHomeRoom,
} from "./homeInterior";

const WORLD_WIDTH = townMap.width * townMap.tilewidth;
const WORLD_HEIGHT = townMap.height * townMap.tileheight;
const AFFORDANCE_LABELS: Readonly<Record<string, string>> = {
  read_notice: "공지 읽기",
  post_notice: "공지 쓰기",
  plan_event: "행사 계획",
  rest: "휴식",
  meet: "만남",
  observe: "관찰",
  sit: "앉기",
  chat: "대화",
};

interface AgentView {
  container: Phaser.GameObjects.Container;
  body: Phaser.GameObjects.Rectangle;
  leftLeg: Phaser.GameObjects.Rectangle;
  rightLeg: Phaser.GameObjects.Rectangle;
  name: string;
  bubbleText: string;
  selected: boolean;
}

function tileKeyAt(x: number, y: number): string {
  const centerX = x * TILE_SIZE + TILE_SIZE / 2;
  const centerY = y * TILE_SIZE + TILE_SIZE / 2;
  const plaza = getLayer("locations").find(
    (location) =>
      getProperty(location, "kind") === "plaza" &&
      contains(location, centerX, centerY),
  );
  if (plaza) return TILE.plaza;

  const park = getLayer("locations").find(
    (location) =>
      getProperty(location, "kind") === "park" &&
      contains(location, centerX, centerY),
  );
  const pond = getLayer("collision").find(
    (collision) =>
      collision.type === "water" && contains(collision, centerX, centerY),
  );
  if (pond) return TILE.water;
  if (park) return (x + y) % 5 === 0 ? TILE.grassDark : TILE.park;
  if (isPathTile(centerX, centerY)) return TILE.path;
  return (x * 3 + y * 5) % 7 === 0 ? TILE.grassDark : TILE.grass;
}

function contains(object: TiledObject, x: number, y: number): boolean {
  return (
    x >= object.x &&
    x < object.x + (object.width ?? 0) &&
    y >= object.y &&
    y < object.y + (object.height ?? 0)
  );
}

function distanceToSegment(
  px: number,
  py: number,
  ax: number,
  ay: number,
  bx: number,
  by: number,
): number {
  const dx = bx - ax;
  const dy = by - ay;
  if (dx === 0 && dy === 0) return Math.hypot(px - ax, py - ay);
  const progress = Phaser.Math.Clamp(
    ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy),
    0,
    1,
  );
  return Math.hypot(px - (ax + progress * dx), py - (ay + progress * dy));
}

function isPathTile(x: number, y: number): boolean {
  return getLayer("paths").some((path) => {
    const points = path.polyline ?? [];
    return points.slice(1).some((point, index) => {
      const previous = points[index];
      return (
        distanceToSegment(
          x,
          y,
          path.x + previous.x,
          path.y + previous.y,
          path.x + point.x,
          path.y + point.y,
        ) <= 25
      );
    });
  });
}

export class MainScene extends Phaser.Scene {
  declare gridEngine: GridEngine;

  private readonly agentViews = new Map<string, AgentView>();
  private readonly homeViews = new Map<string, DollhouseHomeView>();
  private readonly buildingViews = new Map<string, DollhouseBuildingView>();
  private readonly indoorAgentViews = new Map<string, IndoorResidentView>();
  private gridMovement?: ServerGridMovement;
  private unsubscribeStore?: () => void;
  private followedAgentId: string | undefined;
  private cursors?: Phaser.Types.Input.Keyboard.CursorKeys;
  private dragOrigin?: Phaser.Math.Vector2;
  private pinchStartDistance?: number;
  private pinchStartZoom?: number;
  private textOverlay!: GameTextOverlayController;

  constructor() {
    super("MainScene");
  }

  create(): void {
    createPixelTextures(this);
    this.textOverlay = new GameTextOverlayController(this, "world");
    useGameStore.getState().setSceneContext({ kind: "world" });
    this.cameras.main
      .setBackgroundColor("#173b2b")
      .setBounds(0, 0, WORLD_WIDTH, WORLD_HEIGHT);
    this.physics.world.setBounds(0, 0, WORLD_WIDTH, WORLD_HEIGHT);

    this.drawTileWorld();
    this.drawBuildings();
    this.drawDecorations();
    this.drawInteractables();
    this.drawAgents();
    this.initializeGridMovement();
    this.drawWorldTitle();
    this.configureCamera();

    const unsubscribeStore = useGameStore.subscribe((state, previousState) => {
      if (state.agents !== previousState.agents) {
        this.applyAgentStates(state.agents);
      }
      if (state.followRequestId !== previousState.followRequestId) {
        this.followAgent(state.selectedAgentId);
      }
    });
    this.unsubscribeStore = unsubscribeStore;
    this.applyAgentStates(useGameStore.getState().agents);
    const cleanupStoreSubscription = () => {
      unsubscribeStore();
      this.textOverlay.destroy();
      if (this.unsubscribeStore === unsubscribeStore) {
        this.unsubscribeStore = undefined;
      }
    };
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, cleanupStoreSubscription);
    this.events.once(Phaser.Scenes.Events.DESTROY, cleanupStoreSubscription);
  }

  update(_time: number, delta: number): void {
    for (const view of this.agentViews.values()) {
      view.container.setDepth(view.container.y + 40);
    }
    if (this.cursors) {
      const camera = this.cameras.main;
      const speed = (delta / camera.zoom) * 0.48;
      let moved = false;
      if (this.cursors.left.isDown) {
        camera.scrollX -= speed;
        moved = true;
      }
      if (this.cursors.right.isDown) {
        camera.scrollX += speed;
        moved = true;
      }
      if (this.cursors.up.isDown) {
        camera.scrollY -= speed;
        moved = true;
      }
      if (this.cursors.down.isDown) {
        camera.scrollY += speed;
        moved = true;
      }
      if (moved) this.stopFollowing();
    }
    this.textOverlay.sync();
  }

  private drawTileWorld(): void {
    const ground = this.add.container(0, 0).setDepth(0);
    for (let y = 0; y < townMap.height; y += 1) {
      for (let x = 0; x < townMap.width; x += 1) {
        ground.add(
          this.add
            .image(x * TILE_SIZE, y * TILE_SIZE, tileKeyAt(x, y))
            .setOrigin(0),
        );
      }
    }

    const border = this.add.graphics().setDepth(2);
    border.lineStyle(8, 0x245f40, 1);
    border.strokeRect(4, 4, WORLD_WIDTH - 8, WORLD_HEIGHT - 8);
  }

  private drawBuildings(): void {
    for (const location of getLayer("locations")) {
      const kind = getProperty(location, "kind", "building");
      if (kind === "plaza" || kind === "park") continue;
      if (kind === "home") {
        const home = drawDollhouseHome(
          this,
          location,
          parseColor(getProperty(location, "color"), 0xd58c68),
        );
        this.homeViews.set(location.name, home);
        for (const room of HOME_ROOMS) {
          this.textOverlay.add({
            id: `room:${location.name}:${room.id}`,
            text: room.label,
            x: home.x + room.x * home.width + 5,
            y: home.y + room.y * home.height + 4,
            tone: "room",
            anchor: "left-top",
          });
        }
        this.addLocationLabel(location);
        continue;
      }
      this.drawPixelBuilding(location, kind);
      this.addLocationLabel(location);
    }
  }

  private addLocationLabel(location: TiledObject): void {
    this.textOverlay.add({
      id: `location:${location.name}`,
      text: location.name,
      x: location.x + (location.width ?? 0) / 2,
      y: location.y - 4,
      tone: "location",
    });
  }

  private drawPixelBuilding(location: TiledObject, kind: string): void {
    const bodyColor = parseColor(getProperty(location, "color"), 0xd58c68);
    const building = drawDollhouseBuilding(this, location, kind, bodyColor);
    this.buildingViews.set(location.name, building);
    let showEnterLabel = false;
    this.textOverlay.add({
      id: `enter:${location.name}`,
      text: "▼ VIEW",
      x: building.doorX,
      y: building.doorY + 10,
      tone: "action",
      visible: () => showEnterLabel,
    });
    const portal = this.add
      .zone(building.doorX, building.doorY - 11, 48, 48)
      .setDepth(building.depth + 22)
      .setInteractive({ useHandCursor: true });
    portal.on("pointerover", () => {
      showEnterLabel = true;
    });
    portal.on("pointerout", () => {
      showEnterLabel = false;
    });
    portal.on("pointerdown", () => {
      this.scene.start("InteriorScene", {
        name: location.name,
        kind,
        color: getProperty(location, "color", "#d58c68"),
      });
    });
  }

  private drawDecorations(): void {
    for (const decoration of getLayer("decorations")) {
      if (decoration.type === "tree") {
        this.add
          .image(decoration.x, decoration.y, "tree")
          .setOrigin(0.5, 0.72)
          .setDepth(decoration.y + 28);
      } else if (decoration.type === "flowers") {
        this.add
          .image(decoration.x - 16, decoration.y - 16, TILE.flowers)
          .setOrigin(0)
          .setDepth(4);
      } else if (decoration.type === "lamp") {
        this.add
          .image(decoration.x, decoration.y, "lamp")
          .setOrigin(0.5, 0.85)
          .setDepth(decoration.y + 18);
      } else if (decoration.type === "bush") {
        this.add
          .image(decoration.x, decoration.y, "bush")
          .setOrigin(0.5, 0.82)
          .setDepth(decoration.y + 6);
      }
    }
  }

  private drawInteractables(): void {
    for (const item of getLayer("interactables")) {
      if (item.type === "fountain") this.drawFountain(item);
      if (item.type === "notice_board") this.drawNoticeBoard(item);
      if (item.type === "bench") this.drawBench(item);
    }
  }

  private drawFountain(item: TiledObject): void {
    const graphics = this.add.graphics().setDepth(item.y + 28);
    graphics.fillStyle(0x315f68, 1);
    graphics.fillRect(item.x - 39, item.y + 8, 78, 18);
    graphics.fillStyle(0xa8d7d2, 1);
    graphics.fillRect(item.x - 34, item.y, 68, 20);
    graphics.fillStyle(0x4ca6c3, 1);
    graphics.fillRect(item.x - 28, item.y + 3, 56, 12);
    graphics.fillStyle(0xe0f7ea, 1);
    graphics.fillRect(item.x - 4, item.y - 18, 8, 22);
    graphics.fillStyle(0x7acadd, 1);
    graphics.fillRect(item.x - 11, item.y - 12, 22, 5);
    this.bindInteractable(item, 86, 58);
  }

  private drawNoticeBoard(item: TiledObject): void {
    const graphics = this.add.graphics().setDepth(item.y + 24);
    graphics.fillStyle(0x553728, 1);
    graphics.fillRect(item.x - 21, item.y - 25, 42, 31);
    graphics.fillStyle(0xdeb874, 1);
    graphics.fillRect(item.x - 17, item.y - 21, 34, 23);
    graphics.fillStyle(0xf3e5bd, 1);
    graphics.fillRect(item.x - 10, item.y - 16, 14, 11);
    graphics.fillStyle(0x553728, 1);
    graphics.fillRect(item.x - 15, item.y + 4, 6, 22);
    graphics.fillRect(item.x + 9, item.y + 4, 6, 22);
    this.bindInteractable(item, 54, 62);
  }

  private drawBench(item: TiledObject): void {
    const graphics = this.add.graphics().setDepth(item.y + 18);
    graphics.fillStyle(0x66412f, 1);
    graphics.fillRect(item.x - 24, item.y - 8, 48, 8);
    graphics.fillRect(item.x - 24, item.y + 5, 48, 7);
    graphics.fillStyle(0x3e332a, 1);
    graphics.fillRect(item.x - 17, item.y + 11, 5, 10);
    graphics.fillRect(item.x + 12, item.y + 11, 5, 10);
    this.bindInteractable(item, 58, 44);
  }

  private bindInteractable(
    item: TiledObject,
    width: number,
    height: number,
  ): void {
    const affordances = getProperty(item, "affordances")
      .split(",")
      .map((affordance) => affordance.trim())
      .filter((affordance) => affordance.length > 0)
      .map((affordance) => AFFORDANCE_LABELS[affordance] ?? affordance);
    const locationPath = getProperty(item, "location_path");
    const location = locationPath.split(" > ").at(-1) ?? locationPath;
    const zone = this.add
      .zone(item.x, item.y, Math.max(width, 44), Math.max(height, 44))
      .setDepth(item.y + 80)
      .setInteractive({ useHandCursor: true });
    zone.on("pointerdown", () => {
      useGameStore.getState().showInteractionNotice({
        title: item.name,
        description: `${location} · 주민 행동: ${affordances.join(" · ")}`,
      });
    });
  }

  private drawAgents(): void {
    for (const spawn of getLayer("spawns")) {
      // Lowercased to match the backend's `agent_id` (e.g. "jiho"), which is
      // how `applyAgentStates` looks views up on every snapshot. The map's
      // `agent_id` property is capitalized ("Jiho") for map-authoring
      // readability only.
      const id = getProperty(spawn, "agent_id", spawn.name).toLowerCase();
      const color = parseColor(getProperty(spawn, "color"), 0x6487d6);
      const container = this.add
        .container(spawn.x, spawn.y)
        .setDepth(spawn.y + 40)
        .setSize(44, 44)
        .setInteractive()
        // Hidden until the first real snapshot for this agent_id arrives —
        // there is no meaningful "default position" to show; the Tiled
        // spawn coordinate exists only to seed Grid Engine's startPosition
        // and the (indoor) view's initial transform, not as a place to
        // visibly render an agent that hasn't loaded yet.
        .setVisible(false);
      const shadow = this.add.rectangle(0, 13, 22, 7, 0x183328, 0.35);
      const leftLeg = this.add.rectangle(-5, 10, 6, 9, 0x41372f);
      const rightLeg = this.add.rectangle(5, 10, 6, 9, 0x41372f);
      const body = this.add.rectangle(0, 1, 20, 20, color);
      const neck = this.add.rectangle(0, -9, 8, 5, 0xe8ba91);
      const head = this.add.rectangle(0, -17, 17, 15, 0xf1c9a1);
      const hair = this.add.rectangle(
        0,
        -23,
        19,
        7,
        id === "sujin" ? 0x4b2f2c : 0x34302d,
      );
      const fringe = this.add.rectangle(
        -6,
        -19,
        5,
        6,
        id === "sujin" ? 0x4b2f2c : 0x34302d,
      );
      const eyes = this.add.rectangle(0, -16, 10, 2, 0x3d3835);
      container.add([
        shadow,
        leftLeg,
        rightLeg,
        body,
        neck,
        head,
        hair,
        fringe,
        eyes,
      ]);
      container.on("pointerdown", () =>
        useGameStore.getState().selectAgent(id),
      );
      const view: AgentView = {
        container,
        body,
        leftLeg,
        rightLeg,
        name: spawn.name,
        bubbleText: "",
        selected: false,
      };
      this.agentViews.set(id, view);
      this.textOverlay.add({
        id: `agent:${id}:bubble`,
        text: () => view.bubbleText,
        x: () => view.container.x,
        y: () => view.container.y - 38,
        tone: "bubble",
        anchor: "bottom",
        maxWidth: 300,
        visible: () => view.container.visible && view.bubbleText.length > 0,
      });
      this.textOverlay.add({
        id: `agent:${id}:name`,
        text: () => view.name,
        x: () => view.container.x,
        y: () => view.container.y + 28,
        tone: "nameplate",
        selected: () => view.selected,
        visible: () => view.container.visible,
      });
      const indoorView = createIndoorResidentView(this, spawn.name, color);
      indoorView.container.on("pointerdown", () =>
        useGameStore.getState().selectAgent(id),
      );
      this.indoorAgentViews.set(id, indoorView);
      this.textOverlay.add({
        id: `indoor-agent:${id}:bubble`,
        text: () => indoorView.bubbleText,
        x: () => indoorView.container.x,
        y: () => indoorView.container.y - 27,
        tone: "bubble",
        anchor: "bottom",
        maxWidth: 220,
        visible: () =>
          indoorView.container.visible && indoorView.bubbleText.length > 0,
      });
      this.textOverlay.add({
        id: `indoor-agent:${id}:name`,
        text: () => indoorView.name,
        x: () => indoorView.container.x,
        y: () => indoorView.container.y + 15,
        tone: "nameplate",
        anchor: "top",
        selected: () => indoorView.selected,
        visible: () => indoorView.container.visible,
      });
    }
  }

  private initializeGridMovement(): void {
    const navigationTiles = Array.from({ length: townMap.height }, () =>
      Array.from({ length: townMap.width }, () => 0),
    );
    const navigationMap = this.make.tilemap({
      data: navigationTiles,
      tileWidth: TILE_SIZE,
      tileHeight: TILE_SIZE,
    });
    const navigationTileset = navigationMap.addTilesetImage(
      "navigation",
      TILE.grass,
      TILE_SIZE,
      TILE_SIZE,
      0,
      0,
      0,
    );
    if (!navigationTileset) {
      throw new Error("Unable to create Grid Engine navigation tileset");
    }
    const navigationLayer = navigationMap.createLayer(
      navigationMap.layers[0].name,
      navigationTileset,
      0,
      0,
    );
    if (!navigationLayer) {
      throw new Error("Unable to create Grid Engine navigation layer");
    }
    navigationLayer.setVisible(false);
    this.gridEngine.create(navigationMap, {
      numberOfDirections: NumberOfDirections.FOUR,
      characters: getLayer("spawns").flatMap((spawn) => {
        const id = getProperty(spawn, "agent_id", spawn.name).toLowerCase();
        const view = this.agentViews.get(id);
        if (!view) return [];
        return [
          {
            id,
            container: view.container,
            startPosition: {
              x: Math.floor(spawn.x / TILE_SIZE),
              y: Math.floor(spawn.y / TILE_SIZE),
            },
            speed: 2,
            collides: false,
            numberOfDirections: NumberOfDirections.FOUR,
          },
        ];
      }),
    });
    this.gridMovement = new ServerGridMovement(this.gridEngine);
  }

  private applyAgentStates(states: Record<string, SpatialAgentState>): void {
    for (const indoorView of this.indoorAgentViews.values()) {
      indoorView.container.setVisible(false);
    }
    const roomOccupancy = new Map<string, number>();
    const buildingOccupancy = new Map<string, number>();
    for (const [id, state] of Object.entries(states)) {
      // `id` is the backend's lowercase agent_id, which `drawAgents` now
      // keys every view map by directly (see the note there) — no name-based
      // fallback needed, and none would be reliable: `state.name` is the
      // Korean display name, not an English identifier.
      const characterId = id;
      const view = this.agentViews.get(characterId);
      if (!view) continue;
      const home = [...this.homeViews.values()].find((candidate) =>
        isAgentInsideHome(state, candidate.name),
      );
      const building = [...this.buildingViews.values()].find((candidate) =>
        isAgentAtLocation(state, candidate.name),
      );
      const indoorView = this.indoorAgentViews.get(characterId);
      view.container.setVisible(home === undefined && building === undefined);
      if (home && indoorView) {
        const room = resolveHomeRoom(state.current_action, state.plan);
        const occupancyKey = `${home.name}:${room}`;
        const occupancy = roomOccupancy.get(occupancyKey) ?? 0;
        roomOccupancy.set(occupancyKey, occupancy + 1);
        const position = home.roomPositions[room];
        indoorView.container
          .setPosition(position.x + occupancy * 18, position.y)
          .setDepth(home.depth + 12 + occupancy)
          .setVisible(true);
        indoorView.bubbleText = agentBubbleLabel(state);
        indoorView.name = state.name;
        if (this.followedAgentId === characterId) {
          this.cameras.main.startFollow(indoorView.container, true, 0.12, 0.12);
        }
      } else if (building && indoorView) {
        const occupancy = buildingOccupancy.get(building.name) ?? 0;
        buildingOccupancy.set(building.name, occupancy + 1);
        const position =
          building.activityPositions[
            occupancy % building.activityPositions.length
          ];
        if (position) {
          const row = Math.floor(occupancy / building.activityPositions.length);
          indoorView.container
            .setPosition(position.x + row * 18, position.y)
            .setDepth(building.depth + 12 + occupancy)
            .setVisible(true);
          indoorView.bubbleText = agentBubbleLabel(state);
          indoorView.name = state.name;
          if (this.followedAgentId === characterId) {
            this.cameras.main.startFollow(
              indoorView.container,
              true,
              0.12,
              0.12,
            );
          }
        }
      }
      const transition = this.gridMovement?.sync(
        characterId,
        state.tile_position,
      );
      const isMoving = transition?.kind === "cardinal-step";
      view.body.setScale(
        isMoving && Math.abs(transition.deltaX) > 0 ? 0.9 : 1,
        1,
      );
      view.leftLeg.y = isMoving ? 8 : 10;
      view.rightLeg.y = isMoving ? 12 : 10;
      view.bubbleText = agentBubbleLabel(state);
      view.name = state.name;
    }
  }

  private configureCamera(): void {
    const camera = this.cameras.main;
    camera.setZoom(this.scale.width < 720 ? 1.15 : 1.65).setRoundPixels(true);
    this.cursors = this.input.keyboard?.createCursorKeys();
    this.input.addPointer(1);
    this.input.on(
      "wheel",
      (
        _pointer: Phaser.Input.Pointer,
        _objects: Phaser.GameObjects.GameObject[],
        _dx: number,
        dy: number,
      ) => {
        camera.setZoom(Phaser.Math.Clamp(camera.zoom - dy * 0.001, 1, 2.4));
      },
    );
    this.input.on(
      "pointerdown",
      (
        pointer: Phaser.Input.Pointer,
        currentlyOver: Phaser.GameObjects.GameObject[],
      ) => {
        if (this.hasTwoPointersDown()) {
          this.beginPinch();
          this.dragOrigin = undefined;
          return;
        }
        if (!currentlyOver.some((object) => this.isAgentGameObject(object))) {
          this.stopFollowing();
        }
        this.dragOrigin = new Phaser.Math.Vector2(pointer.x, pointer.y);
      },
    );
    this.input.on("pointermove", (pointer: Phaser.Input.Pointer) => {
      if (this.hasTwoPointersDown()) {
        const distance = this.pointerDistance();
        if (
          this.pinchStartDistance === undefined ||
          this.pinchStartZoom === undefined
        ) {
          this.beginPinch();
          return;
        }
        this.stopFollowing();
        camera.setZoom(
          Phaser.Math.Clamp(
            this.pinchStartZoom * (distance / this.pinchStartDistance),
            1,
            2.4,
          ),
        );
        this.dragOrigin = undefined;
        return;
      }
      if (!pointer.isDown || !this.dragOrigin) return;
      const dx = pointer.x - this.dragOrigin.x;
      const dy = pointer.y - this.dragOrigin.y;
      if (Math.abs(dx) + Math.abs(dy) < 3) return;
      this.stopFollowing();
      camera.scrollX -= dx / camera.zoom;
      camera.scrollY -= dy / camera.zoom;
      this.dragOrigin.set(pointer.x, pointer.y);
    });
    this.input.on("pointerup", () => {
      this.pinchStartDistance = undefined;
      this.pinchStartZoom = undefined;
      this.dragOrigin = undefined;
    });
    this.followAgent(useGameStore.getState().selectedAgentId);
  }

  private isAgentGameObject(object: Phaser.GameObjects.GameObject): boolean {
    for (const view of this.agentViews.values()) {
      if (view.container === object) return true;
    }
    for (const view of this.indoorAgentViews.values()) {
      if (view.container === object) return true;
    }
    return false;
  }

  private hasTwoPointersDown(): boolean {
    return this.input.pointer1.isDown && this.input.pointer2.isDown;
  }

  private pointerDistance(): number {
    return Phaser.Math.Distance.Between(
      this.input.pointer1.x,
      this.input.pointer1.y,
      this.input.pointer2.x,
      this.input.pointer2.y,
    );
  }

  private beginPinch(): void {
    this.pinchStartDistance = Math.max(this.pointerDistance(), 1);
    this.pinchStartZoom = this.cameras.main.zoom;
  }

  private followAgent(id: string): void {
    const characterId = [...this.agentViews.keys()].find(
      (candidate) => candidate.toLocaleLowerCase() === id.toLocaleLowerCase(),
    );
    if (!characterId) return;
    const view = this.agentViews.get(characterId);
    if (!view) return;
    this.followedAgentId = characterId;
    const indoorView = this.indoorAgentViews.get(characterId);
    const target = indoorView?.container.visible
      ? indoorView.container
      : view.container;
    this.cameras.main.startFollow(target, true, 0.12, 0.12);
    for (const [agentId, candidate] of this.agentViews) {
      const selected = agentId === characterId;
      candidate.selected = selected;
      const indoorCandidate = this.indoorAgentViews.get(agentId);
      if (indoorCandidate) indoorCandidate.selected = selected;
    }
  }

  private stopFollowing(): void {
    this.cameras.main.stopFollow();
    // Clear the followed agent, not just the Phaser follow lock — otherwise
    // the next agent-state update re-locks the camera onto them (e.g. via
    // the indoor startFollow calls in applyAgentStates) the moment they
    // step into a home/building, undoing the user's manual pan.
    this.followedAgentId = undefined;
  }

  private drawWorldTitle(): void {
    this.textOverlay.add({
      id: "world:title",
      text: "BRIAR COVE",
      x: 34,
      y: 36,
      tone: "title",
      anchor: "left-top",
    });
  }
}
