import { createRequire } from 'node:module';
import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Arcade·Matter 물리를 쓰지 않으니 물리를 뺀 Phaser 진입점을 쓴다. 타입은 `phaser` 패키지 것을 그대로 쓴다.
// 패키지 `exports`가 하위 경로를 막고 있어 파일 경로를 직접 찾는다.
const phaserNoPhysics = path.join(
  path.dirname(createRequire(import.meta.url).resolve('phaser/package.json')),
  'src/phaser-no-physics.js',
);

// `town.json`(Tiled)은 백엔드와 공유하는 packages/shared/maps 에서 정적 파일로 서빙한다 (SPEC §15).
// QA 훅(window.render_game_to_text / advanceTime)은 dev 서버와 `--mode qa` 빌드에만 들어간다.
export default defineConfig(({ command, mode }) => ({
  plugins: [react(), tailwindcss()],
  publicDir: '../shared/maps',
  resolve: {
    alias: [{ find: /^phaser$/, replacement: phaserNoPhysics }],
  },
  define: {
    __QA_HOOKS__: JSON.stringify(command === 'serve' || mode === 'qa'),
  },
  build: {
    rollupOptions: {
      output: {
        // Phaser는 따로 캐시되도록 vendor 청크로 분리한다.
        manualChunks(id) {
          if (id.includes('/node_modules/phaser/')) return 'phaser';
          return undefined;
        },
      },
    },
  },
  server: {
    port: 3000,
  },
}));
