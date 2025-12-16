import React, { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph from "force-graph";

const HUB_ID = "polystep";
const DEFAULT_PAN_PADDING_PX = 24;
const PAN_LIMIT_PX = 30; // 화면 드래그 허용 범위(아주 조금만)

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
  {
    id: "gov24",
    label: "정부24",
    url: "https://www.gov.kr/",
    summary:
      "정부 서비스·지원 정책을 한 곳에서 검색하고 신청/민원 안내까지 확인할 수 있는 통합 포털이에요.",
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
  const lockedZoomRef = useRef(null);
  const baseCenterRef = useRef({ x: 0, y: 0 }); // 팬 제한 기준점(초기/fit 후 중심)
  const didInitialFitRef = useRef(false);
  const didPostLayoutFitRef = useRef(false);
  const hoverNodeRef = useRef(null);

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
      // 기본 pan 사용(일반적인 '잡고 끌기' 느낌). 카메라 느낌(역방향) 제거.
      .enablePanInteraction(true)
      // 확대/축소(휠/트랙패드/핀치) 인터랙션 비활성화: 공간(스케일) 고정
      .enableZoomInteraction(false);

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

    // 기본적으로는 줌을 잠그되, 초기 fit에서 계산된 스케일을 우선으로 사용합니다.
    // (enableZoomInteraction(false)로 사용자 줌은 불가)
    if (typeof lockedZoomRef.current === "number") {
      fg.minZoom(lockedZoomRef.current).maxZoom(lockedZoomRef.current);
    } else {
      fg.minZoom(minZoom).maxZoom(maxZoom);
    }

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
      // 노드 간 거리(퍼짐)를 "약간" 줄이기 위해 반발을 조금 완화
      if (charge?.strength) charge.strength(-190);
      if (charge?.distanceMin) charge.distanceMin(24);
      if (charge?.distanceMax) charge.distanceMax(900);

      const link = fg.d3Force("link");
      // 링크 거리도 소폭 감소(허브-사이트 / 사이트-사이트)
      if (link?.distance)
        link.distance((l) =>
          l?.source?.id === HUB_ID || l?.target?.id === HUB_ID ? 128 : 109
        );
      if (link?.strength) link.strength(1);
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

    // 드래그 중 '무거운 저항(강)' 적용:
    // - 커서 위치로 바로 점프하지 않고, fx/fy가 목표를 천천히 따라오게(스프링/lerp)
    // - 드래그 중 속도도 감쇠해 "무거운 물체" 느낌 강화
    fg.onNodeDrag((node, translate) => {
      if (!node) return;

      const followFactor = 0.28; // 강한 저항(작을수록 더 무거움)
      const tx = finiteOr(translate?.x, 0);
      const ty = finiteOr(translate?.y, 0);

      const targetFx = finiteOr(node.x, 0) + tx;
      const targetFy = finiteOr(node.y, 0) + ty;

      const curFx = node.fx == null ? finiteOr(node.x, 0) : finiteOr(node.fx, finiteOr(node.x, 0));
      const curFy = node.fy == null ? finiteOr(node.y, 0) : finiteOr(node.fy, finiteOr(node.y, 0));

      node.fx = curFx + (targetFx - curFx) * followFactor;
      node.fy = curFy + (targetFy - curFy) * followFactor;

      // 드래그 중 관성 폭주 방지(무게감)
      node.vx = finiteOr(node.vx, 0) * 0.6;
      node.vy = finiteOr(node.vy, 0) * 0.6;
    });
    fg.onNodeDragEnd((node, translate) => {
      // 드래그 직후 바로 fx/fy 해제하면 "휙" 돌아가며 딱딱해 보일 수 있어,
      // 잠깐 유지 후 풀고, 관성/탄성 느낌을 위해 속도를 살짝 부여합니다.
      if (!node) return;

      node.fx = node.x;
      node.fy = node.y;

      // 강하게 느리게: 놓을 때 튀는 힘을 줄여서 빨리 돌아가는 느낌을 완화
      const impulse = 0.025;
      node.vx = (node.vx ?? 0) + (translate?.x ?? 0) * impulse;
      node.vy = (node.vy ?? 0) + (translate?.y ?? 0) * impulse;

      if (timersRef.current.releaseFx) clearTimeout(timersRef.current.releaseFx);
      timersRef.current.releaseFx = setTimeout(() => {
        node.fx = undefined;
        node.fy = undefined;
        fg.d3ReheatSimulation?.();
      }, 260);

      // 드래그 직후 살짝 더 느리게(감쇠↓) 보이게 했다가 원복
      if (timersRef.current.restoreDecay) clearTimeout(timersRef.current.restoreDecay);
      const prevDecay = fg.d3VelocityDecay?.();
      // 감쇠를 크게 올려서(더 감속) 복귀 속도를 강하게 낮춤
      if (typeof prevDecay === "number") fg.d3VelocityDecay(0.24);
      timersRef.current.restoreDecay = setTimeout(() => {
        if (typeof prevDecay === "number") fg.d3VelocityDecay(prevDecay);
      }, 1200);
    });
    fg.nodeCanvasObject((node, ctx, globalScale) => {
      const x = finiteOr(node.x, 0);
      const y = finiteOr(node.y, 0);

      const isHovered = hoverNode?.id === node.id;
      const isNeighbor = neighborIds.has(node.id);
      // 노드 크기 상향(가독성↑)
      const baseR = node.kind === "hub" ? 28 : 20;
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
      const baseR = node.kind === "hub" ? 32 : 24;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, baseR, 0, 2 * Math.PI, false);
      ctx.fill();
    });
    // 팬/줌 종료 시: 줌 범위 클램프 + 그래프가 화면 밖으로 나가지 않도록 중심 클램프
    fg.onZoomEnd(() => {
      // 사용자 줌은 비활성화 상태이므로, 여기서는 경계 튕김만 처리합니다.
      const k = fg.zoom?.() ?? lockedZoomRef.current ?? 1;
      const maxDeltaGraph = PAN_LIMIT_PX / (isFiniteNumber(k) && k > 0 ? k : 1);
      const cur = fg.centerAt?.() ?? { x: 0, y: 0 };
      const curX = finiteOr(cur?.x, 0);
      const curY = finiteOr(cur?.y, 0);

      const base = baseCenterRef.current ?? { x: 0, y: 0 };
      const targetX = clamp(curX, base.x - maxDeltaGraph, base.x + maxDeltaGraph);
      const targetY = clamp(curY, base.y - maxDeltaGraph, base.y + maxDeltaGraph);

      // 제한 범위를 넘어갔으면 살짝 튕기듯 돌아오게
      if (targetX !== curX || targetY !== curY) {
        runBoundaryBounce({
          fg,
          width: fg.width?.() ?? 0,
          height: fg.height?.() ?? 0,
          paddingPx: 0,
          attemptCenter: { x: curX, y: curY },
          timersRef,
        });
        fg.centerAt(targetX, targetY, 120);
      }
    });

    // 드래그 중에도 너무 멀리 못 가게 즉시 클램프(체감상 "아주 조금만" 이동)
    fg.onZoom?.(() => {
      const k = fg.zoom?.() ?? lockedZoomRef.current ?? 1;
      const maxDeltaGraph = PAN_LIMIT_PX / (isFiniteNumber(k) && k > 0 ? k : 1);
      const cur = fg.centerAt?.() ?? { x: 0, y: 0 };
      const curX = finiteOr(cur?.x, 0);
      const curY = finiteOr(cur?.y, 0);
      const base = baseCenterRef.current ?? { x: 0, y: 0 };
      const targetX = clamp(curX, base.x - maxDeltaGraph, base.x + maxDeltaGraph);
      const targetY = clamp(curY, base.y - maxDeltaGraph, base.y + maxDeltaGraph);
      if (targetX !== curX || targetY !== curY) {
        fg.centerAt(targetX, targetY, 0);
      }
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

        // 2. 현재 fit 스케일을 "고정 줌"으로 잠금(확대/축소 불가)
        const k = fg.zoom();
        if (isFiniteNumber(k) && k > 0) {
          lockedZoomRef.current = k;
          fg.minZoom(k).maxZoom(k);
        }

        // 3. 팬 제한 기준점 업데이트(항상 중앙 기준에서 아주 조금만 이동 가능)
        const c = fg.centerAt?.();
        if (c && isFiniteNumber(c.x) && isFiniteNumber(c.y)) {
          baseCenterRef.current = { x: c.x, y: c.y };
        } else {
          baseCenterRef.current = { x: 0, y: 0 };
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
