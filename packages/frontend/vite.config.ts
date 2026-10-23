import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// `town.json`(Tiled)은 백엔드와 공유하는 packages/shared/maps 에서 정적 파일로 서빙한다 (SPEC §15).
// QA 훅(window.render_game_to_text / advanceTime)은 dev 서버와 `--mode qa` 빌드에만 들어간다.
// Phaser는 공식 ESM 번들을 쓴다. 물리를 뺀 `src/phaser-no-physics.js`는 webpack 전용 가정(DefinePlugin 플래그,
// 조건부 require, `global`)이 있어 Vite에서 dev·build 모두 깨진다.
export default defineConfig(({ command, mode }) => ({
  plugins: [react(), tailwindcss()],
  publicDir: '../shared/maps',
  define: {
    __QA_HOOKS__: JSON.stringify(command === 'serve' || mode === 'qa'),
  },
  build: {
    rollupOptions: {
      output: {
        // Phaser는 게임 청크가 동적으로 불러오고, 따로 캐시되도록 vendor 청크로 분리한다.
        manualChunks(id) {
          // commonjs 헬퍼는 진입 청크도 쓴다. phaser 청크에 넣으면 진입 청크가 phaser를 정적으로 끌어온다.
          if (id.includes('commonjsHelpers')) return 'vendor';
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
