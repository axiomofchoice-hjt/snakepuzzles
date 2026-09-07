import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command }) => ({
  plugins: [react()],
  // 生产构建部署到 GitHub Pages 项目站点(/snakepuzzles/)时用该 base，
  // 本地 dev 仍用根路径，避免访问地址变化。
  base: command === 'build' ? '/snakepuzzles/' : '/',
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
}));
