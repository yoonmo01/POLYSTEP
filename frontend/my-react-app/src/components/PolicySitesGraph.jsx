import React, { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph from "force-graph";

const HUB_ID = "polystep";
const DEFAULT_PAN_PADDING_PX = 24;

// 추후 사이트를 늘릴 때는 이 배열에 항목만 추가하면 됩니다.
const DEFAULT_SITE_CATALOG = [
  {
    id: "ontong_youth",
    label: "온통청년",
    url: "https://www.youthcenter.go.kr/",
    summary:
      "청년정책포털. 중앙/지자체 청년정책 정보를 한 곳에서 조회하고 신청 정보를 확인할 수 있어요.",
    kind: "site",
  },
  {
    id: "kosaf",
    label: "한국장학재단",
    url: "https://www.kosaf.go.kr/",
    summary:
      "장학금/학자금대출 등 학비 지원 정보를 제공하고 신청 절차를 안내하는 공식 기관이에요.",
    kind: "site",
  },
];

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function isFiniteNumber(n) {
  return typeof n === "number" && Number.isFinite(n);
}

function finiteOr(value, fallback) {
  return isFiniteNumber(value) ? value : fallback;
}

function computeClampedCenterToKeepBboxInView(fg, width, height, paddingPx) {
  if (!fg || !width || !height) return;
  if (typeof fg.getGraphBbox !== "function" || typeof fg.centerAt !== "function") return;

  const bbox = fg.getGraphBbox?.();
  if (!bbox?.x || !bbox?.y) return;

  const k = typeof fg.zoom === "function" ? fg.zoom() : 1;
  if (!isFiniteNumber(k) || k <= 0) return;
  const halfW = width / 2 / k;
  const halfH = height / 2 / k;
  const padGX = (paddingPx ?? 0) / k;
  const padGY = (paddingPx ?? 0) / k;

  const [rawMinX, rawMaxX] = bbox.x;
  const [rawMinY, rawMaxY] = bbox.y;
  if (
    !isFiniteNumber(rawMinX) ||
    !isFiniteNumber(rawMaxX) ||
    !isFiniteNumber(rawMinY) ||
    !isFiniteNumber(rawMaxY)
  ) {
    return;
  }

  const minX = Math.min(rawMinX, rawMaxX);
  const maxX = Math.max(rawMinX, rawMaxX);
  const minY = Math.min(rawMinY, rawMaxY);
  const maxY = Math.max(rawMinY, rawMaxY);

  // 현재 중심
  const curCenter = typeof fg.centerAt === "function" ? fg.centerAt() : { x: 0, y: 0 };
  const curX = isFiniteNumber(curCenter?.x) ? curCenter.x : 0;
  const curY = isFiniteNumber(curCenter?.y) ? curCenter.y : 0;

  // bbox가 뷰포트보다 크면(모두를 한 화면에 못 넣으면) bbox 중심으로 맞춥니다.
  const viewportW = Math.max(0, halfW - padGX);
  const viewportH = Math.max(0, halfH - padGY);

  const minAllowedX = maxX - viewportW;
  const maxAllowedX = minX + viewportW;
  const minAllowedY = maxY - viewportH;
  const maxAllowedY = minY + viewportH;

  let targetX = curX;
  let targetY = curY;

  if (minAllowedX <= maxAllowedX) {
    targetX = clamp(curX, minAllowedX, maxAllowedX);
  } else {
    targetX = (minX + maxX) / 2;
  }

  if (minAllowedY <= maxAllowedY) {
    targetY = clamp(curY, minAllowedY, maxAllowedY);
  } else {
    targetY = (minY + maxY) / 2;
  }

  return { curX, curY, targetX, targetY, zoom: k, didClamp: targetX !== curX || targetY !== curY };
}

function runBoundaryBounce({
  fg,
  width,
  height,
  paddingPx,
  attemptCenter,
  timersRef,
}) {
  if (!fg) return;
  const clampInfo = computeClampedCenterToKeepBboxInView(fg, width, height, paddingPx);
  if (!clampInfo?.didClamp) return;

  const { targetX, targetY, zoom } = clampInfo;
  const attemptX = finiteOr(attemptCenter?.x, clampInfo.curX);
  const attemptY = finiteOr(attemptCenter?.y, clampInfo.curY);

  const overshootX = attemptX - targetX;
  const overshootY = attemptY - targetY;
  const overshootMag = Math.hypot(overshootX, overshootY) || 0;
  if (overshootMag < 1e-6) return;

  const bounceGraphUnits = (14 / (zoom || 1)) * 1.0;
  const scale = Math.min(0.22, bounceGraphUnits / overshootMag);
  const bounceX = targetX - overshootX * scale;
  const bounceY = targetY - overshootY * scale;

  // 기존 bounce 타이머 정리
  if (timersRef?.current?.bounce1) clearTimeout(timersRef.current.bounce1);
  if (timersRef?.current?.bounce2) clearTimeout(timersRef.current.bounce2);

  fg.centerAt(targetX, targetY, 90);
  if (timersRef?.current) {
    timersRef.current.bounce1 = setTimeout(() => {
      fg.centerAt(bounceX, bounceY, 140);
    }, 95);
    timersRef.current.bounce2 = setTimeout(() => {
      fg.centerAt(targetX, targetY, 220);
    }, 255);
  }
}

export default function PolicySitesGraph({
  sites = DEFAULT_SITE_CATALOG,
  // 노드 간격을 넓히면 전체 bbox가 커져 초기 fit이 더 큰 줌아웃을 필요로 합니다.
  // 그래서 minZoom을 너무 높게 잡지 않습니다(노드가 잘리는 문제 방지).
  minZoom = 0.35,
  maxZoom = 2.2,
}) {
  const containerRef = useRef(null); // React가 관리하는 래퍼(툴팁 포함)
  const stageRef = useRef(null); // force-graph가 캔버스를 붙이는 전용 컨테이너(React 자식 없음)
  const fgRef = useRef(null); // force-graph instance
  const timersRef = useRef({
    releaseFx: null,
    restoreDecay: null,
    bounce1: null,
    bounce2: null,
  });
  const didInitialFitRef = useRef(false);
  const didPostLayoutFitRef = useRef(false);
  const hoverNodeRef = useRef(null);
  const isPanningRef = useRef(false);
  const lastPointerRef = useRef({ x: 0, y: 0, id: null });
  const attemptedCenterRef = useRef(null);
  const didHitWallRef = useRef(false);

  const [size, setSize] = useState({ width: 0, height: 0 });
  const [hoverNode, setHoverNode] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const graphData = useMemo(() => {
    const nodes = [
      {
        id: HUB_ID,
        label: "POLYSTEP",
        kind: "hub",
        summary:
          "여러 청년 정책/장학 사이트 정보를 한 번에 모아, 사용자가 이해하기 쉽게 안내하는 통합 서비스예요.",
      },
      ...sites.map((s) => ({
        id: s.id,
        label: s.label,
        url: s.url,
        summary: s.summary,
        kind: s.kind ?? "site",
      })),
    ];

    const links = sites.map((s) => ({
      source: HUB_ID,
      target: s.id,
    }));

    return { nodes, links };
  }, [sites]);

  // 데이터가 바뀌면 초기 fit을 다시 수행할 수 있도록 reset
  useEffect(() => {
    didInitialFitRef.current = false;
    didPostLayoutFitRef.current = false;
  }, [graphData]);

  const neighborIds = useMemo(() => {
    const set = new Set();
    if (!hoverNode) return set;

    const hoveredId = hoverNode.id;
    for (const l of graphData.links) {
      const src = typeof l.source === "object" ? l.source.id : l.source;
      const tgt = typeof l.target === "object" ? l.target.id : l.target;
      if (src === hoveredId) set.add(tgt);
      if (tgt === hoveredId) set.add(src);
    }
    return set;
  }, [graphData.links, hoverNode]);

  useEffect(() => {
    if (!containerRef.current) return;

    // 일부 환경(구형 브라우저/특수 웹뷰)에서는 ResizeObserver가 없을 수 있어,
    // 없으면 window resize 기반으로 fallback 합니다. (흰 화면 방지)
    if (typeof ResizeObserver === "function") {
      const ro = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (!entry) return;
        const { width, height } = entry.contentRect;
        setSize({ width: Math.floor(width), height: Math.floor(height) });
      });

      ro.observe(containerRef.current);
      return () => ro.disconnect();
    }

    const update = () => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setSize({ width: Math.floor(rect.width), height: Math.floor(rect.height) });
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  // force-graph 인스턴스는 "마운트 시 1회 생성/언마운트 시 1회 정리"로 유지합니다.
  // React 자식(툴팁 등)과 캔버스 DOM이 섞이면 removeChild 충돌이 날 수 있어 stageRef로 분리합니다.
  useEffect(() => {
    if (!stageRef.current) return;

    const fg = ForceGraph()(stageRef.current)
      .backgroundColor("rgba(0,0,0,0)")
      .enableNodeDrag(true)
      // 기본 pan을 끄고(충돌 방지) 우리가 커스텀 팬을 제어합니다.
      .enablePanInteraction(false);

    fgRef.current = fg;

    return () => {
      try {
        if (timersRef.current.releaseFx) clearTimeout(timersRef.current.releaseFx);
        if (timersRef.current.restoreDecay) clearTimeout(timersRef.current.restoreDecay);
        if (timersRef.current.bounce1) clearTimeout(timersRef.current.bounce1);
        if (timersRef.current.bounce2) clearTimeout(timersRef.current.bounce2);
        fgRef.current?._destructor?.();
      } catch {
        // dev StrictMode 등에서 이중 정리 타이밍이 발생할 수 있어 방어
      } finally {
        fgRef.current = null;
      }
    };
  }, []);

  // 그래프 옵션/데이터 업데이트 (인스턴스 생성 후)
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;

    fg.minZoom(minZoom).maxZoom(maxZoom);

    // [수정] 렌더링 전에 물리 연산을 미리 수행하여 노드 위치를 잡습니다.
    // 이렇게 하면 처음에 노드가 뭉쳐 있다가 퍼지는 과정 없이 바로 정돈된 상태로 나옵니다.
    fg.cooldownTicks(100);

    fg.graphData(graphData);

    // 초기 화면 정렬은 size가 잡힌 뒤 별도 effect에서 수행합니다.

    // 노드 간격/안정화(붙어있는 문제 완화)
    // - 반발(charge) 강화
    // - 링크 거리 증가
    // - 감쇠를 낮춰(관성↑) 너무 빨리 복원되는 느낌 완화
    try {
      fg.d3VelocityDecay(0.22);

      const charge = fg.d3Force("charge");
      if (charge?.strength) charge.strength(-260);
      if (charge?.distanceMin) charge.distanceMin(24);
      if (charge?.distanceMax) charge.distanceMax(900);

      const link = fg.d3Force("link");
      if (link?.distance) link.distance((l) => (l?.source?.id === HUB_ID || l?.target?.id === HUB_ID ? 170 : 130));
      if (link?.strength) link.strength(0.9);
    } catch {
      // force 옵션이 환경에 따라 다를 수 있어 방어
    }

    fg.linkColor(() =>
      hoverNode ? "rgba(191, 219, 254, 0.22)" : "rgba(148, 163, 184, 0.18)"
    );
    fg.linkWidth((link) => {
      if (!hoverNode) return 1;
      const src = typeof link.source === "object" ? link.source.id : link.source;
      const tgt = typeof link.target === "object" ? link.target.id : link.target;
      const hoveredId = hoverNode.id;
      const isAdjacent = src === hoveredId || tgt === hoveredId;
      return isAdjacent ? 2 : 1;
    });
    fg.onNodeHover((node) => {
      hoverNodeRef.current = node || null;
      setHoverNode(node || null);
    });
    fg.onNodeClick((node) => {
      if (!node?.url) return;
      window.open(node.url, "_blank", "noopener,noreferrer");
    });
    fg.onNodeDragEnd((node, translate) => {
      // 드래그 직후 바로 fx/fy 해제하면 "휙" 돌아가며 딱딱해 보일 수 있어,
      // 잠깐 유지 후 풀고, 관성/탄성 느낌을 위해 속도를 살짝 부여합니다.
      if (!node) return;

      node.fx = node.x;
      node.fy = node.y;

      // 작은 임펄스로 튕김 느낌
      const impulse = 0.03;
      node.vx = (node.vx ?? 0) + (translate?.x ?? 0) * impulse;
      node.vy = (node.vy ?? 0) + (translate?.y ?? 0) * impulse;

      if (timersRef.current.releaseFx) clearTimeout(timersRef.current.releaseFx);
      timersRef.current.releaseFx = setTimeout(() => {
        node.fx = undefined;
        node.fy = undefined;
        fg.d3ReheatSimulation?.();
      }, 160);

      // 드래그 직후 살짝 더 느리게(감쇠↓) 보이게 했다가 원복
      if (timersRef.current.restoreDecay) clearTimeout(timersRef.current.restoreDecay);
      const prevDecay = fg.d3VelocityDecay?.();
      if (typeof prevDecay === "number") fg.d3VelocityDecay(0.16);
      timersRef.current.restoreDecay = setTimeout(() => {
        if (typeof prevDecay === "number") fg.d3VelocityDecay(prevDecay);
      }, 520);
    });
    fg.nodeCanvasObject((node, ctx, globalScale) => {
      const x = finiteOr(node.x, 0);
      const y = finiteOr(node.y, 0);

      const isHovered = hoverNode?.id === node.id;
      const isNeighbor = neighborIds.has(node.id);
      // 노드 크기 상향(가독성↑)
      const baseR = node.kind === "hub" ? 14 : 10;
      const r = isHovered ? baseR * 1.35 : isNeighbor ? baseR * 1.15 : baseR;

      if (!isFiniteNumber(r) || r <= 0) return;

      const grad = ctx.createRadialGradient(
        x - r * 0.25,
        y - r * 0.25,
        r * 0.2,
        x,
        y,
        r
      );

      if (node.kind === "hub") {
        grad.addColorStop(0, "rgba(255, 255, 255, 0.35)");
        grad.addColorStop(1, "rgba(59, 130, 246, 0.95)");
      } else {
        grad.addColorStop(0, "rgba(255, 255, 255, 0.25)");
        grad.addColorStop(1, "rgba(148, 163, 184, 0.9)");
      }

      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI, false);
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.lineWidth = Math.max(1, 1.2 / globalScale);
      ctx.strokeStyle = isHovered
        ? "rgba(255, 255, 255, 0.9)"
        : "rgba(226, 232, 255, 0.45)";
      ctx.stroke();

      const label = node.label ?? String(node.id);
      const fontSize = clamp(12 / globalScale, 9, 16);
      ctx.font = `${fontSize}px ui-sans-serif, system-ui, -apple-system, "Segoe UI", "Apple SD Gothic Neo", sans-serif`;
      ctx.fillStyle = "rgba(245, 247, 255, 0.92)";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(label, x, y + r + 2 / globalScale);
    });
    fg.nodePointerAreaPaint((node, color, ctx) => {
      const x = finiteOr(node.x, 0);
      const y = finiteOr(node.y, 0);
      const baseR = node.kind === "hub" ? 16 : 12;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, baseR, 0, 2 * Math.PI, false);
      ctx.fill();
    });
    // 팬/줌 종료 시: 줌 범위 클램프 + 그래프가 화면 밖으로 나가지 않도록 중심 클램프
    fg.onZoomEnd(() => {
      const k = fg.zoom();
      const clamped = clamp(k, minZoom, maxZoom);
      if (clamped !== k) fg.zoom(clamped, 80);

      runBoundaryBounce({
        fg,
        width: fg.width?.() ?? 0,
        height: fg.height?.() ?? 0,
        paddingPx: DEFAULT_PAN_PADDING_PX,
        attemptCenter: null,
        timersRef,
      });
    });

    // [수정] 엔진 정지 시 확실하게 중앙으로 이동
    fg.onEngineStop(() => {
      fg.zoomToFit(400, DEFAULT_PAN_PADDING_PX);
    });

    // [추가] 데이터 로드 직후 강제 중앙 정렬 (setTimeout으로 렌더링 큐 확보)
    const fitTimer = setTimeout(() => {
      fg.zoomToFit(0, DEFAULT_PAN_PADDING_PX); // 즉시 이동
    }, 50);

    return () => clearTimeout(fitTimer);
  }, [graphData, hoverNode, neighborIds, minZoom, maxZoom]);

  const handleMouseMove = (e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const width = size.width || 800;
  const height = size.height || 520;

  // 커스텀 "카메라 느낌" 팬(역방향):
  // - 배경을 드래그하면 카메라 중심이 드래그 방향으로 이동 → 그래프는 반대로 움직이는 체감
  useEffect(() => {
    const stageEl = stageRef.current;
    const fg = fgRef.current;
    if (!stageEl || !fg) return;

    const onPointerDown = (e) => {
      if (e.button !== 0) return;
      if (hoverNodeRef.current) return; // 노드 위에서는 팬 시작하지 않음(노드 드래그 우선)

      isPanningRef.current = true;
      lastPointerRef.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
      attemptedCenterRef.current = null;
      didHitWallRef.current = false;

      stageEl.setPointerCapture?.(e.pointerId);
    };

    const onPointerMove = (e) => {
      if (!isPanningRef.current) return;
      if (lastPointerRef.current.id !== e.pointerId) return;

      const dx = e.clientX - lastPointerRef.current.x;
      const dy = e.clientY - lastPointerRef.current.y;
      lastPointerRef.current = { x: e.clientX, y: e.clientY, id: e.pointerId };

      const k = fg.zoom?.() ?? 1;
      if (!isFiniteNumber(k) || k <= 0) return;

      const cur = fg.centerAt?.() ?? { x: 0, y: 0 };
      const curX = finiteOr(cur?.x, 0);
      const curY = finiteOr(cur?.y, 0);

      // 카메라 느낌(역방향): 드래그 방향으로 카메라 중심 이동
      const nextX = curX + dx / k;
      const nextY = curY + dy / k;
      fg.centerAt(nextX, nextY, 0);

      // 경계 밖으로는 못 나가게 즉시 클램프(벽에 '붙는' 느낌)
      const clampInfo = computeClampedCenterToKeepBboxInView(
        fg,
        width,
        height,
        DEFAULT_PAN_PADDING_PX
      );
      if (clampInfo?.didClamp) {
        didHitWallRef.current = true;
        attemptedCenterRef.current = { x: nextX, y: nextY };
        fg.centerAt(clampInfo.targetX, clampInfo.targetY, 0);
      }
    };

    const endPan = (e) => {
      if (!isPanningRef.current) return;
      isPanningRef.current = false;
      stageEl.releasePointerCapture?.(e.pointerId);

      // 벽에 닿으려고 밀었던 경우에만 튕김 애니메이션을 실행
      if (didHitWallRef.current) {
        runBoundaryBounce({
          fg,
          width,
          height,
          paddingPx: DEFAULT_PAN_PADDING_PX,
          attemptCenter: attemptedCenterRef.current,
          timersRef,
        });
      }
    };

    stageEl.addEventListener("pointerdown", onPointerDown);
    stageEl.addEventListener("pointermove", onPointerMove);
    stageEl.addEventListener("pointerup", endPan);
    stageEl.addEventListener("pointercancel", endPan);

    return () => {
      stageEl.removeEventListener("pointerdown", onPointerDown);
      stageEl.removeEventListener("pointermove", onPointerMove);
      stageEl.removeEventListener("pointerup", endPan);
      stageEl.removeEventListener("pointercancel", endPan);
    };
  }, [width, height]);

  // 사이즈 변경 시 그래프 캔버스 사이즈 반영
  useEffect(() => {
    if (!fgRef.current) return;
    if (typeof fgRef.current.width === "function") fgRef.current.width(width);
    if (typeof fgRef.current.height === "function") fgRef.current.height(height);

    // [수정] 너비/높이가 유효할 때, 무조건 한 번 fit을 시도하도록 변경
    // requestAnimationFrame을 사용하여 캔버스 리사이즈가 DOM에 반영된 직후 실행
    if (width > 0 && height > 0) {
      const rafId = requestAnimationFrame(() => {
        const fg = fgRef.current;
        if (!fg) return;

        // 1. 화면에 딱 맞게 줌 (여백 포함)
        fg.zoomToFit(200, DEFAULT_PAN_PADDING_PX);

        // 2. 줌 레벨이 너무 작거나 크면 보정
        const k = fg.zoom();
        const clamped = clamp(k, minZoom, maxZoom);
        if (clamped !== k) {
          fg.zoom(clamped, 200);
        }
      });

      return () => cancelAnimationFrame(rafId);
    }
  }, [width, height, maxZoom, minZoom]); // minZoom 의존성 추가

  return (
    <div
      className="policy-graph"
      ref={containerRef}
      onMouseMove={handleMouseMove}
      role="img"
      aria-label="POLYSTEP 청년 정책 사이트 통합 그래프"
    >
      <div className="policy-graph-stage" ref={stageRef} />
      {hoverNode && (
        <div
          className="policy-graph-tooltip"
          style={{
            left: clamp(mousePos.x + 12, 12, width - 290),
            top: clamp(mousePos.y + 12, 12, height - 100),
          }}
        >
          <div className="policy-graph-tooltip-title">{hoverNode.label}</div>
          <div className="policy-graph-tooltip-body">{hoverNode.summary}</div>
          {hoverNode.url && (
            <div className="policy-graph-tooltip-hint">
              클릭하면 사이트로 이동합니다
            </div>
          )}
        </div>
      )}
    </div>
  );
}
