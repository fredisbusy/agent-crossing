import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// `town.json`(Tiled)은 백엔드와 공유하는 packages/shared/maps 에서 정적 파일로 서빙한다 (SPEC §15).
// QA 훅(window.render_game_to_text / advanceTime)은 dev 서버와 `--mode qa` 빌드에만 들어간다.
export default defineConfig(({ command, mode }) => ({
  plugins: [react(), tailwindcss()],
  publicDir: '../shared/maps',
  define: {
    __QA_HOOKS__: JSON.stringify(command === 'serve' || mode === 'qa'),
  },
  server: {
    port: 3000,
  },
}));
