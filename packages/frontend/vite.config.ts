import { createRequire } from 'node:module';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Arcade·Matter 물리를 쓰지 않으니 물리를 뺀 Phaser 진입점을 쓴다. 타입은 `phaser` 패키지 것을 그대로 쓴다.
// 패키지 `exports`가 하위 경로를 막고 있어 파일 경로를 직접 찾는다.
const phaserNoPhysics = path.join(
  path.dirname(createRequire(import.meta.url).resolve('phaser/package.json')),
  'src/phaser-no-physics.js',
);

// Phaser 소스(CommonJS)는 webpack DefinePlugin이 `typeof FLAG`를 true/false로 바꿔 주는 것을 전제로 한다.
// 그대로 두면 `typeof WEBGL_DEBUG`가 문자열 "undefined"라 참이 되어 설치되지 않은 `phaser3spectorjs`를 require한다.
// 값은 Phaser의 config/webpack.config.js를 따르되, 디버그(WEBGL_DEBUG)와 실험·3D·Facebook 플러그인은 끈다.
const PHASER_FLAGS: Readonly<Record<string, boolean>> = {
  CANVAS_RENDERER: true,
  WEBGL_RENDERER: true,
  FEATURE_SOUND: true,
  WEBGL_DEBUG: false,
  EXPERIMENTAL: false,
  PLUGIN_3D: false,
  PLUGIN_CAMERA3D: false,
  PLUGIN_FBINSTANT: false,
};
const PHASER_FLAG_PATTERN = new RegExp(`typeof (${Object.keys(PHASER_FLAGS).join('|')})\\b`, 'g');
const PHASER_SOURCE = /[\\/]node_modules[\\/]phaser[\\/]src[\\/].*\.js$/;

function replacePhaserFlags(code: string): string {
  return code.replace(PHASER_FLAG_PATTERN, (_match, flag: string) => String(PHASER_FLAGS[flag]));
}

const phaserFlagsPlugin: Plugin = {
  name: 'phaser-flags',
  enforce: 'pre',
  transform(code, id) {
    return PHASER_SOURCE.test(id) ? { code: replacePhaserFlags(code), map: null } : null;
  },
};

// `town.json`(Tiled)은 백엔드와 공유하는 packages/shared/maps 에서 정적 파일로 서빙한다 (SPEC §15).
// QA 훅(window.render_game_to_text / advanceTime)은 dev 서버와 `--mode qa` 빌드에만 들어간다.
export default defineConfig(({ command, mode }) => ({
  plugins: [phaserFlagsPlugin, react(), tailwindcss()],
  // dev 사전 번들(esbuild)은 Vite 플러그인을 거치지 않으니 같은 치환을 esbuild 플러그인으로 한다.
  optimizeDeps: {
    esbuildOptions: {
      plugins: [
        {
          name: 'phaser-flags',
          setup(build) {
            build.onLoad({ filter: PHASER_SOURCE }, (args) => ({
              contents: replacePhaserFlags(readFileSync(args.path, 'utf8')),
              loader: 'js',
            }));
          },
        },
      ],
    },
  },
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
