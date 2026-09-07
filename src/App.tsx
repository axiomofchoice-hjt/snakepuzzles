import { useState, useRef, useEffect, useCallback } from 'react';
import { createState, applyMove, DIR_KEY } from './game';
import type { Direction, GameState, Status } from './game';
import { LEVELS } from './levels';
import Board from './components/Board';
import Panel from './components/Panel';

const fresh = (index: number): GameState => createState(LEVELS[index]);

export default function App() {
  const [hardMode, setHardMode] = useState(false);
  const [level, setLevel] = useState(0);
  const [game, setGame] = useState<GameState>(() => fresh(0));
  const [snapKey, setSnapKey] = useState(0); // 重置/揭示时递增，让动画直接落到目标
  const baseRef = useRef<GameState | null>(null); // 初始快照（困难模式盲走时显示）
  if (baseRef.current === null) baseRef.current = game;

  const reset = useCallback((lvl: number = level): void => {
    const st = fresh(lvl);
    baseRef.current = st;
    setGame(st);
    setLevel(lvl);
    setSnapKey((k) => k + 1);
  }, [level]);

  const move = useCallback((dir: Direction): void => {
    setGame((prev) => {
      if (!prev || prev.status !== 'playing') return prev;
      const next = applyMove(prev, dir);
      // 简单模式：撞墙/撞自己不算失败，蛇原地不动、继续游戏（不计次数）
      if (!hardMode && next.status === 'lost') return prev;
      return next;
    });
  }, [hardMode]);

  const setMode = useCallback((hard: boolean): void => {
    setHardMode(hard);
    reset();
  }, [reset]);

  const goLevel = useCallback((n: number): void => {
    if (n < 0 || n >= LEVELS.length) return;
    reset(n);
  }, [reset]);

  // 困难模式在结束时揭示：动画直接落到最终状态；简单模式保持最后一步的移动动画
  const prevStatusRef = useRef<Status>(game.status);
  useEffect(() => {
    if (prevStatusRef.current === 'playing' && game.status !== 'playing' && hardMode) {
      setSnapKey((k) => k + 1);
    }
    prevStatusRef.current = game.status;
  }, [game.status, hardMode]);

  // 键盘控制
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      const dir = DIR_KEY[e.key];
      if (dir) { e.preventDefault(); move(dir); return; }
      const k = e.key.toLowerCase();
      if (k === 'r') reset();
      else if (k === 'm') setMode(!hardMode);
      else if (/^[1-9]$/.test(k) && Number(k) <= LEVELS.length) goLevel(Number(k) - 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [move, reset, setMode, hardMode, goLevel]);

  const playing = game && game.status === 'playing';
  // 困难模式：进行中只显示初始快照；到终点/失败才显示结果
  const shown = hardMode && playing ? baseRef.current : game;

  return (
    <main className="app">
      <header className="topbar">
        <div className="brand">
          <h1>贪吃蛇解密</h1>
          <span className="sub">snakepuzzles</span>
        </div>
        <div className="toolbar">
          <div className="levels">
            {LEVELS.map((_, i) => (
              <button
                key={i}
                className={`btn level ${i === level ? 'active' : ''}`}
                onClick={() => goLevel(i)}
                title={`第 ${i + 1} 关`}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <button className={`btn ${hardMode ? 'primary' : ''}`} onClick={() => setMode(!hardMode)}>
            模式：{hardMode ? '困难' : '简单'}
          </button>
          <button className="btn" onClick={() => reset()}>重新开始</button>
        </div>
      </header>

      <div className="layout">
        <div className="stage">
          <Board state={shown} snapKey={snapKey} onMove={move} controlHead={game.snake[0]} />
        </div>
        <Panel
          game={game}
          hardMode={hardMode}
        />
      </div>
    </main>
  );
}
