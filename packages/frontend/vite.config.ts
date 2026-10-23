import { readdirSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// 런타임이 publicDir에서 요청하는 파일(town-map.ts, mock-town.ts의 `town.json`). 편집용 그림·README는 배포하지 않는다.
const RUNTIME_PUBLIC_FILES: ReadonlySet<string> = new Set(['town.json']);

// 빌드가 직접 만드는 이름. publicDir에 같은 이름이 생겨도 지우지 않는다.
const BUILD_OUTPUT_NAMES: ReadonlySet<string> = new Set(['index.html']);

// 빌드 뒤 outDir에 복사된 publicDir 항목 중 런타임 파일이 아닌 것을 지운다(dev 서버는 publicDir 전체를 그대로 서빙).
function pruneEditorOnlyPublicFiles(): Plugin {
  let publicDir = '';
  let outDir = '';
  let assetsDir = '';
  return {
    name: 'prune-editor-only-public-files',
    apply: 'build',
    configResolved(config) {
      publicDir = config.publicDir;
      outDir = resolve(config.root, config.build.outDir);
      assetsDir = config.build.assetsDir;
    },
    closeBundle() {
      if (publicDir === '') return;
      for (const name of readdirSync(publicDir)) {
        if (RUNTIME_PUBLIC_FILES.has(name) || BUILD_OUTPUT_NAMES.has(name) || name === assetsDir) continue;
        rmSync(join(outDir, name), { recursive: true, force: true });
      }
    },
  };
}

// `town.json`(Tiled)은 백엔드와 공유하는 packages/shared/maps 에서 정적 파일로 서빙한다 (SPEC §15).
// QA 훅(window.render_game_to_text / advanceTime)은 dev 서버와 `--mode qa` 빌드에만 들어간다.
// Phaser는 공식 ESM 번들을 쓴다. 물리를 뺀 `src/phaser-no-physics.js`는 webpack 전용 가정(DefinePlugin 플래그,
// 조건부 require, `global`)이 있어 Vite에서 dev·build 모두 깨진다.
export default defineConfig(({ command, mode }) => ({
  plugins: [react(), tailwindcss(), pruneEditorOnlyPublicFiles()],
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
