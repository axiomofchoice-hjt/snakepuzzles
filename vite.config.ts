import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // 默认根路径 '/'（适配 CloudBase 等根路径托管）；
  // GitHub Pages 项目站点由 CI 通过环境变量 VITE_BASE=/snakepuzzles/ 传入。
  base: process.env.VITE_BASE ?? '/',
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
});
