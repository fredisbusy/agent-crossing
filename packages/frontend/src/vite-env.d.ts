/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 월드 WebSocket 주소. 없으면 접속한 호스트의 8000 포트로 만든다. */
  readonly VITE_WORLD_SOCKET_URL?: string;
}
