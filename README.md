# 贪吃蛇解密 (snakepuzzles)

一款结合了经典贪吃蛇与迷宫解谜的网页小游戏：在环形边界的迷宫里移动蛇，吃到钥匙、开门、绕过墙，让蛇头抵达终点。

## 玩法

- 蛇头每按一次方向键前进一格，蛇身跟随，蛇尾逐步腾空。
- 网格四周**环形**：出界会从另一侧进入。
- **墙 `#`**：撞到即失败。
- **钥匙（小写字母）**：吃到后打开所有同字母的门（`a` 开所有 `A`，`b` 开所有 `B`）。
- **门（大写字母）**：吃对应钥匙前是墙，撞上即失败；吃到钥匙后变地板。
- **终点 `D`**：蛇头到达即胜利。
- 撞到墙或自己（除即将腾空的蛇尾外）均失败（简单模式除外，见下）。

> 钥匙与门外观相同、匹配隐藏，需要记忆谁对应谁。

## 模式

- **简单模式**：实时显示移动；撞墙/撞自己不算失败，蛇原地不动、继续游戏。
- **困难模式**：不显示移动（盲走），只显示初始状态；到达终点或失败才揭示结果。

## 操作

| 操作 | 方式 |
| --- | --- |
| 移动 | `WASD` / 方向键；鼠标点击蛇头相邻格，或按住鼠标拖动连续移动 |
| 重新开始 | `R` |
| 切换简单 / 困难模式 | `M` |
| 切换关卡 | `1`–`9` |

> 鼠标的“相邻”也包含穿过边界：例如蛇头在左缘，点击右缘的相邻格也会穿过去。按住后拖动，每滑过一格就朝该方向走一步。

## 关卡

内置 9 个关卡，从基础的直线布局到带钥匙/门、蛇身更长的迷宫。关卡数据在 `src/levels.ts`，用 `src/game.ts` 的 `parseLevel` 将 ASCII 迷宫（`H` 蛇头、`0` 地板、`#` 墙、`D` 终点、大写字母门、小写字母钥匙、制表符蛇身）转成结构化对象。

## 本地运行

需要 Node.js（建议 18+）。

```bash
npm install
npm run dev      # 开发服务器 http://127.0.0.1:5173
npm run build    # 构建到 dist/
npm run preview  # 本地预览构建产物
```

## 部署到 GitHub Pages

本仓库配置了 CI（`.github/workflows/deploy.yml`）：push 到 `main`/`master` 或手动触发时执行 `npm ci && npm run build`，并用 `peaceiris/actions-gh-pages` 把 `dist/` 发布到 **`gh-pages`** 分支。

生产构建的 `base` 为 `/snakepuzzles/`（见 `vite.config.ts`），对应项目站点地址：

```
https://<用户名>.github.io/snakepuzzles/
```

使用步骤：

1. 在仓库 **Settings → Pages → Source** 选择 **Deploy from a branch**，分支选 `gh-pages`。
2. 推送代码后由 CI 自动构建并更新 `gh-pages`。

## 技术栈

- [React](https://react.dev/) 18
- [Vite](https://vitejs.dev/) 5 + [TypeScript](https://www.typescriptlang.org/)
- 纯逻辑（无 React/DOM 依赖）放在 `src/game.ts`，便于单测与逻辑验证（`npm run test`）

## 目录结构

```
src/
  App.tsx            # 应用状态/键盘控制/模式与关卡切换
  game.ts            # 纯游戏逻辑（移动、钥匙门、环形边界、关卡解析）
  levels.ts          # 关卡数据
  components/
    Board.tsx        # 棋盘与蛇的 SVG 渲染/爬行动画（含边界环绕、转向）
    Panel.tsx        # 状态、图例、操作说明
  main.tsx           # 入口
  styles.css         # 样式
```

## License

[MIT](./LICENSE)
