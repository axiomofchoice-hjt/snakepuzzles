import { useMemo, useState, useEffect, useRef } from 'react';
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react';
import { tileAt, isDoorChar, isKeyChar } from '../game';
import type { Cell, Direction, GameState } from '../game';

const GAP = 2;            // 格子间距
const TARGET_W = 560;     // 让整张图放进该空间
const TARGET_H = 520;

interface Pt { x: number; y: number; }
interface Vec { dr: number; dc: number; }
interface Eye { ex: number; ey: number; er: number; pr: number; px: number; py: number; }
interface Display { pts: Pt[]; dir: Vec; }

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

function wrapLerp(a: Pt, b: Pt, e: number, bw: number, bh: number): Pt {
  // 先取 b 相对 a 的最近等价点，再在其间插值（实际环绕算术都在 toward 中）
  const w = toward(a, b, bw, bh);
  return { x: a.x + (w.x - a.x) * e, y: a.y + (w.y - a.y) * e };
}

/*
 * 爬行动画：蛇头伸出、蛇尾收回；穿越边界时沿“最短环绕路径”滑动，头/尾会贴着边缘滑出再滑入。
 */
function useAnimateSnake(snake: Cell[], snapKey: number, cell: number, bw: number, bh: number, W: number, H: number): Display {
  const stride = cell + GAP;
  const center = (c: Cell): Pt => ({ x: c.c * stride + cell / 2, y: c.r * stride + cell / 2 });
  const toPts = (cells: Cell[]): Pt[] => cells.map(center);
  const fallbackDir: Vec = { dr: 1, dc: 0 };
  const restState = (cells: Cell[]): Display => ({ pts: toPts(cells), dir: dirOf(cells, W, H) || fallbackDir });

  const [display, setDisplay] = useState<Display>(() => restState(snake));
  const prevCellsRef = useRef<Cell[]>(snake);
  const rafRef = useRef<number>(0);
  const lastSnap = useRef<number | undefined>(undefined);
  const lastCell = useRef<number>(cell);

  useEffect(() => {
    const to = toPts(snake);
    if (snapKey !== lastSnap.current || cell !== lastCell.current) {
      lastSnap.current = snapKey;
      lastCell.current = cell;
      prevCellsRef.current = snake;
      setDisplay(restState(snake));
      return;
    }
    if (prevCellsRef.current === snake) return;

    const fromCells = prevCellsRef.current;
    prevCellsRef.current = snake;
    const fromPts = fromCells.map(center);
    const oldHead = fromPts[0], oldTail = fromPts[fromPts.length - 1];
    const newHead = to[0], newTail = to[to.length - 1];
    const body = to.slice(1);
    const oldDir = dirOf(fromCells, W, H) || fallbackDir;
    const newDir = dirOf(snake, W, H) || oldDir;

    const start = performance.now();
    cancelAnimationFrame(rafRef.current);
    const step = (t: number): void => {
      const p = Math.min(1, (t - start) / 150);
      const e = easeOutCubic(p);
      // 头/尾沿“最短环绕路径”滑动（贴着边滑出另一边界），实现缓缓滑出滑入
      const head = wrapLerp(oldHead, newHead, e, bw, bh);
      const tail = wrapLerp(oldTail, newTail, e, bw, bh);
      const pts = [head, ...body, tail];
      // 蛇头从一个方向平滑旋转到另一个方向，避免转向开始时在旧蛇头位置闪现“转向后的蛇头”
      const dir = lerpDir(oldDir, newDir, e);
      setDisplay({ pts, dir });
      if (p < 1) rafRef.current = requestAnimationFrame(step);
      else setDisplay(restState(snake));
    };
    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [snake, snapKey, cell, bw, bh, W, H]);

  return display;
}

// 只根据蛇身点求蛇头朝向；返回 null 表示无法确定（蛇头没有相邻身体格）。
// 用边界尺寸 W/H 对行、列差做“最短环绕”处理，穿越边界后方向才不会反。
function dirOf(snake: Cell[], W: number, H: number): Vec | null {
  const h = snake[0], n = snake[1];
  if (n) {
    let dc = h.c - n.c;
    if (W) { if (dc > W / 2) dc -= W; else if (dc < -W / 2) dc += W; }
    let dr = h.r - n.r;
    if (H) { if (dr > H / 2) dr -= H; else if (dr < -H / 2) dr += H; }
    const sdc = Math.sign(dc), sdr = Math.sign(dr);
    if (sdr || sdc) return { dr: sdr, dc: sdc };
  }
  return null;
}

// 在动画里平滑地从旧朝向 a 旋转到新朝向 b（仍是单位向量）
function lerpDir(a: Vec, b: Vec, e: number): Vec {
  if (!a) return b; if (!b) return a;
  if (e <= 0) return a; if (e >= 1) return b;
  const a1 = Math.atan2(a.dr, a.dc), a2 = Math.atan2(b.dr, b.dc);
  let da = a2 - a1;
  while (da > Math.PI) da -= 2 * Math.PI;
  while (da < -Math.PI) da += 2 * Math.PI;
  const ang = a1 + da * e;
  return { dr: Math.sin(ang), dc: Math.cos(ang) };
}

function eyes(p: Pt, dir: Vec, w: number): Eye[] {
  const dx = dir.dc, dy = dir.dr;
  const px = -dy, py = dx;
  const front = w * 0.26, spread = w * 0.40;
  const er = Math.max(3, w * 0.19), pr = er * 0.55;
  const r2 = (n: number): number => Math.round(n * 10) / 10;
  const list: Eye[] = [];
  for (const sgn of [1, -1]) {
    const ex = p.x + dx * front + px * spread * sgn;
    const ey = p.y + dy * front + py * spread * sgn;
    list.push({ ex: r2(ex), ey: r2(ey), er: r2(er), pr: r2(pr), px: r2(ex + dx * er * 0.35), py: r2(ey + dy * er * 0.35) });
  }
  return list;
}

// 把点移近 ref（环绕时取最近的等价位置），换“无横跨线”的局部连接
function toward(ref: Pt, p: Pt, bw: number, bh: number): Pt {
  let x = p.x, y = p.y;
  if (ref.x - x > bw / 2) x += bw; else if (x - ref.x > bw / 2) x -= bw;
  if (ref.y - y > bh / 2) y += bh; else if (y - ref.y > bh / 2) y -= bh;
  return { x, y };
}

/*
 * 生成一条“环绕感知”的连续折线：相邻两点始终走最短环绕路径（用 toward 取最近等价点），
 * 因此穿越边界时不会在棋盘中间画出横贯的长线，而是贴着边缘滑出、滑入。
 * 由于这是一条连续折线（而非按缝切成多段的小折线），动画中头/尾滑动时不会出现
 * “缝连接段”闪现/消失，也就消除了穿过边界那一行/列的浅绿色闪烁。
 */
function buildPolyline(pts: Pt[], bw: number, bh: number): Pt[] {
  const poly = [pts[0]];
  let acc = pts[0];
  for (let i = 1; i < pts.length; i++) {
    acc = toward(acc, pts[i], bw, bh);
    poly.push(acc);
  }
  return poly;
}

const polyToD = (s: Pt[]): string => s.map((p, i) => (i ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1)).join(' ');

// 两点（格子坐标）间的方向；两者恰好相邻时返回方向，否则 null
function dirFrom(fr: number, fc: number, tr: number, tc: number, W: number, H: number): Direction | null {
  let dc = tc - fc; if (W) { if (dc > W / 2) dc -= W; else if (dc < -W / 2) dc += W; }
  let dr = tr - fr; if (H) { if (dr > H / 2) dr -= H; else if (dr < -H / 2) dr += H; }
  if (dr === 1 && dc === 0) return 'down';
  if (dr === -1 && dc === 0) return 'up';
  if (dr === 0 && dc === 1) return 'right';
  if (dr === 0 && dc === -1) return 'left';
  return null;
}

// 拖动时按“优势轴”给方向（按指针物理移动方向，不取环绕捷径）
interface BoardProps {
  state: GameState;
  snapKey?: number;
  onMove: (dir: Direction) => boolean;
  controlHead?: Cell;
}

export default function Board({ state, snapKey = 0, onMove, controlHead }: BoardProps) {
  let cell = Math.floor(Math.min(
    (TARGET_W - (state.W - 1) * GAP) / state.W,
    (TARGET_H - (state.H - 1) * GAP) / state.H
  ));
  cell = Math.max(16, Math.min(46, cell));
  const stride = cell + GAP;
  const snakeW = Math.max(14, Math.min(46, Math.round(cell * 0.66)));
  const bw = state.W * stride - GAP;
  const bh = state.H * stride - GAP;

  // 鼠标/触摸：点击蛇头相邻格移动，按住拖动到蛇头相邻格连续移动
  const boardRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<boolean>(false);

  const cellFromPoint = (x: number, y: number): Cell => {
    const c = Math.max(0, Math.min(state.W - 1, Math.floor(x / stride)));
    const r = Math.max(0, Math.min(state.H - 1, Math.floor(y / stride)));
    return { r, c };
  };

  const pointerCell = (e: ReactPointerEvent<HTMLDivElement>): Cell => {
    const rect = boardRef.current!.getBoundingClientRect();
    return cellFromPoint(e.clientX - rect.left, e.clientY - rect.top);
  };

  const handlePointerDown = (e: ReactPointerEvent<HTMLDivElement>): void => {
    e.preventDefault();
    e.currentTarget.setPointerCapture && e.currentTarget.setPointerCapture(e.pointerId);
    const cell = pointerCell(e);
    dragRef.current = true;
    // 用真实游戏蛇头（controlHead）判断方向：只有点击到蛇头相邻格才移动
    const h = controlHead || state.snake[0];
    const dir = dirFrom(h.r, h.c, cell.r, cell.c, state.W, state.H);
    if (dir) onMove(dir);
  };

  const handlePointerMove = (e: ReactPointerEvent<HTMLDivElement>): void => {
    if (!dragRef.current) return;
    const cell = pointerCell(e);
    // 每次都用真实蛇头重算方向，且要求鼠标位于相邻格才移动。
    // 这样被墙挡住时蛇头不动，方向始终相对蛇头，鼠标不会与移动位置漂移。
    const h = controlHead || state.snake[0];
    const dir = dirFrom(h.r, h.c, cell.r, cell.c, state.W, state.H);
    if (dir) onMove(dir);
  };

  const handlePointerEnd = (): void => { dragRef.current = false; };

  const tiles = useMemo(() => {
    const arr: JSX.Element[] = [];
    for (let r = 0; r < state.H; r++) {
      for (let c = 0; c < state.W; c++) {
        const t = tileAt(state, r, c);
        let cls = t === '#' ? 'wall' : t === '0' ? 'floor' : '';
        if (t === 'D') cls = 'dest';
        else if (isDoorChar(t)) cls = 'door';
        else if (isKeyChar(t)) cls = 'key';
        arr.push(<div key={`${r},${c}`} className={`cell ${cls}`} />);
      }
    }
    return arr;
  }, [state]);

  const { pts: ptsAnim, dir } = useAnimateSnake(state.snake, snapKey, cell, bw, bh, state.W, state.H);
  const d = polyToD(buildPolyline(ptsAnim, bw, bh));
  const head = ptsAnim[0];
  const eyeList = eyes(head, dir, snakeW);

  // 环绕镜像：把整条蛇（折线 + 蛇头）在四周的等价位置各画一份，配合 viewBox 裁剪，
  // 穿越边界时身体能贴着边缘连续滑出滑入，不会“直接出现在另一边”，也不闪烁。
  const wrapOffsets: [number, number][] = [
    [0, 0], [bw, 0], [-bw, 0], [0, bh], [0, -bh],
    [bw, bh], [-bw, -bh], [bw, -bh], [-bw, bh],
  ];

  return (
    <div
      ref={boardRef}
      className="board"
      style={{ '--cell': cell + 'px', width: bw, height: bh } as CSSProperties}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerEnd}
      onPointerCancel={handlePointerEnd}
      onPointerLeave={handlePointerEnd}
    >
      <div
        className="grid"
        style={{
          gridTemplateColumns: `repeat(${state.W}, ${cell}px)`,
          gridTemplateRows: `repeat(${state.H}, ${cell}px)`,
          gap: `${GAP}px`,
        }}
      >
        {tiles}
      </div>

      <svg className="snake-layer" viewBox={`0 0 ${bw} ${bh}`} width={bw} height={bh}>
        {wrapOffsets.map(([ox, oy], i) => (
          <path key={`s${i}`} d={d} fill="none" stroke="#2f7d35" strokeWidth={snakeW + 5} strokeLinecap="round" strokeLinejoin="round" opacity={0.3} transform={`translate(${ox} ${oy})`} />
        ))}
        {wrapOffsets.map(([ox, oy], i) => (
          <path key={`m${i}`} d={d} fill="none" stroke="#69bf6d" strokeWidth={snakeW} strokeLinecap="round" strokeLinejoin="round" transform={`translate(${ox} ${oy})`} />
        ))}
        {wrapOffsets.map(([ox, oy], i) => (
          <g key={`h${i}`} transform={`translate(${ox} ${oy})`}>
            <circle cx={head.x} cy={head.y} r={snakeW / 2} fill="#4caf50" />
            {eyeList.map((e, j) => (
              <g key={j}>
                <circle cx={e.ex} cy={e.ey} r={e.er} fill="#f6fbf6" />
                <circle cx={e.px} cy={e.py} r={e.pr} fill="#1f2b1f" />
              </g>
            ))}
          </g>
        ))}
      </svg>
    </div>
  );
}
