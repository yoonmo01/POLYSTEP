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
  {
    id: "seoul_scholarship",
    label: "서울장학재단",
    url: "https://www.hissf.or.kr/",
    summary:
      "서울 시민과 학생들을 위한 다양한 장학금 지원 및 인재 양성 프로그램을 운영하는 재단입니다.",
    kind: "site",
  },
  {
    id: "work24",
    label: "고용24",
    url: "https://www.work24.go.kr/",
    summary:
      "청년 일자리, 내일배움카드, 국민취업지원제도 등 취업 준비부터 역량 강화까지 필요한 모든 고용 서비스를 한 번에 해결할 수 있어요.",
    kind: "site",
  },
  {
    id: "dreamspon",
    label: "드림스폰",
    url: "https://www.dreamspon.com/",
    summary:
      "전국 대학생 장학금, 대외활동, 공모전 정보를 한눈에 볼 수 있는 장학금 통합 포털입니다.",
    kind: "site",
  },
  {
    id: "samsung_dream",
    label: "삼성꿈장학재단",
    url: "https://www.sdream.or.kr/",
    summary:
      "다양한 교육 소외계층 학생들에게 장학금과 멘토링 프로그램을 지원하는 국내 최대 규모 민간 장학재단입니다.",
    kind: "site",
  },
  {
    id: "bokjiro",
    label: "복지로",
    url: "https://www.bokjiro.go.kr/",
    summary:
      "대한민국 대표 복지포털로, 청년 주거급여, 청년월세지원 등 나에게 필요한 모든 복지 서비스를 찾고 신청할 수 있습니다.",
    kind: "site",
  },
  {
    id: "gw_youth",
    label: "강원청년포털",
    url: "https://job.gwd.go.kr/",
    summary:
      "강원특별자치도 청년들을 위한 일자리, 주거, 복지, 문화 등 분야별 맞춤형 청년 정책 정보를 통합 제공합니다.",
    kind: "site",
  },
  {
    id: "seoul_youth",
    label: "청년몽땅정보통",
    url: "https://youth.seoul.go.kr/",
    summary:
      "서울시 청년 정책의 모든 것. 청년수당, 대중교통비 지원, 역세권 청년주택 등 서울 청년을 위한 정보를 한곳에 모았습니다.",
    kind: "site",
  },
  {
    id: "k_startup",
    label: "K-Startup",
    url: "https://www.k-startup.go.kr/",
    summary:
      "예비창업패키지, 초기창업패키지 등 청년 창업가를 위한 정부 지원 사업과 교육, 공간 정보를 총망라한 창업 지원 포털입니다.",
    kind: "site",
  },
  {
    id: "gg_youth",
    label: "잡아바(경기)",
    url: "https://www.jobaba.net/",
    summary:
      "경기도 일자리재단이 운영하는 통합 플랫폼으로, 청년기본소득, 면접수당 등 경기도 청년 맞춤형 정책을 신청할 수 있습니다.",
    kind: "site",
  },
  {
    id: "busan_youth",
    label: "부산청년플랫폼",
    url: "https://www.busan.go.kr/young",
    summary:
      "부산 청년들을 위한 일자리, 주거, 문화, 복지 정책 정보를 제공하고 '청년디딤돌카드' 등 주요 사업 신청을 받습니다.",
    kind: "site",
  },
  {
    id: "incheon_youth",
    label: "인천유스톡톡",
    url: "https://www.chungbuk.go.kr/young",
    summary:
      "인천 청년들을 위한 취/창업 지원, 모임 공간 대관, 역량 강화 프로그램 등 다양한 청년 활동 지원 정보를 제공합니다.",
    kind: "site",
  },
  {
    id: "gwangju_youth",
    label: "광주청년드림",
    url: "https://youth.gwangju.go.kr/",
    summary:
      "광주 청년들의 구직 활동 수당, 청년 저축 계좌 등 자립과 성장을 돕는 맞춤형 청년 정책을 소개합니다.",
    kind: "site",
  },
  {
    id: "daejeon_youth",
    label: "대전청년포털",
    url: "https://www.daejeonyouthportal.kr/",
    summary:
      "대전 청년 취업 희망 카드, 주택 임차 보증금 이자 지원 등 대전시의 핵심 청년 지원 사업을 안내합니다.",
    kind: "site",
  },
  {
    id: "ulsan_youth",
    label: "울산청년정책플랫폼",
    url: "https://www.ulsan.go.kr/s/ulsanyouth/main.ulsan",
    summary:
      "울산 청년들을 위한 일자리, 주거, 복지 정책 정보와 'U-Dream' 등 지역 특화 청년 지원 사업을 확인할 수 있습니다.",
    kind: "site",
  },
  {
    id: "sejong_youth",
    label: "세종청년플랫폼",
    url: "https://www2.sejong.go.kr/youth/",
    summary:
      "세종시 청년들을 위한 정책, 공간, 문화 활동 정보를 통합 제공하며 청년 간의 소통을 지원하는 플랫폼입니다.",
    kind: "site",
  },
  {
    id: "jeju_youth",
    label: "제주청년센터",
    url: "https://jejuyouth.com/",
    summary:
      "제주 청년들의 역량 강화, 커뮤니티 활동, 취/창업 상담 등 제주 지역 청년 활동의 거점 역할을 하는 온라인 플랫폼입니다.",
    kind: "site",
  },
  {
    id: "cb_youth",
    label: "충북청년포털",
    url: "https://www.chungbuk.go.kr/young",
    summary:
      "충청북도 청년들을 위한 행복 결혼 공제, 학자금 대출 이자 지원 등 지역 맞춤형 청년 복지 정보를 제공합니다.",
    kind: "site",
  },
  {
    id: "cn_youth",
    label: "충남청년포털",
    url: "https://youth.chungnam.go.kr/",
    summary:
      "충청남도 청년들이 일자리·주거·복지·문화·정신건강 등 각종 청년 지원정책과 사업 정보를 한 번에 찾고 신청할 수 있는 종합 정보 사이트입니다.",
    kind: "site",
  },
  {
    id: "jb_youth",
    label: "전북청년허브",
    url: "https://www.jb2030.or.kr/",
    summary:
      "전라북도 청년 정책 통합 검색, 청년 공간 안내, 동아리 지원 등 전북 청년들의 활발한 활동을 지원합니다.",
    kind: "site",
  },
  {
    id: "gn_youth",
    label: "경남청년정보플랫폼",
    url: "https://youth.gyeongnam.go.kr/",
    summary:
      "경상남도 청년들을 위한 맞춤형 정책 검색 서비스와 청년 패스, 면접 정장 대여 등 실질적인 지원 혜택을 안내합니다.",
    kind: "site",
  },
  {
    id: "myhome",
    label: "마이홈포털",
    url: "https://www.myhome.go.kr/",
    summary:
      "국토교통부 주거 복지 포털로, 청년·신혼부부를 위한 주택 공급, 전·월세금 및 주거비 지원 등 각종 주거복지 정책을 한곳에서 조회하고 자가진단까지 할 수 있는 통합 안내 사이트입니다.",
    kind: "site",
  }
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

// 문자열 기반으로 0~1 사이의 안정적인 난수 값을 만들기(매 렌더/매 프레임마다 바뀌지 않게)
function stableRand01(seed) {
  const str = String(seed ?? "");
  let h = 2166136261; // FNV-1a 32-bit
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  // 0..1
  return (h >>> 0) / 4294967295;
}

function clampAbs(v, maxAbs) {
  if (!isFiniteNumber(v)) return 0;
  const m = Math.abs(maxAbs);
  if (!isFiniteNumber(m) || m <= 0) return v;
  return clamp(v, -m, m);
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

  // bbox가 뷰포트보다 크면 bbox 중심으로.
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
  minZoom = 0.35,
  maxZoom = 2.2,
}) {
  const containerRef = useRef(null); // React가 관리하는 래퍼
  const stageRef = useRef(null); // force-graph가 캔버스를 붙이는 전용 컨테이너
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

    // 링크 거리는 "랜덤"처럼 보이되, 매 프레임마다 바뀌면 어색하게 흔들립니다.
    // 그래서 링크마다 한 번 계산한 값을 고정해서 사용합니다.
    const links = sites.map((s) => {
      const u = stableRand01(`${HUB_ID}->${s.id}`);
      const linkDistance = 50 + u * 130; // 링크 길이
      return {
        source: HUB_ID,
        target: s.id,
        linkDistance,
      };
    });

    return { nodes, links };
  }, [sites]);

  // 데이터가 바뀌면 초기 fit을 다시 수행할 수 있도록 reset
  useEffect(() => {
    didInitialFitRef.current = false;
    didPostLayoutFitRef.current = false;
  }, [graphData]);

  // 호버로 인해 graph 설정(useEffect)이 다시 실행되며 시뮬레이션이 '재가열'되는 문제를 막기 위해,
  // 이웃 관계는 "그래프 데이터 기준으로만" 한 번 계산해두고, 렌더링에서는 hoverNodeRef로만 판별합니다.
  const adjacencyMap = useMemo(() => {
    const map = new Map();
    for (const l of graphData.links) {
      const src = typeof l.source === "object" ? l.source.id : l.source;
      const tgt = typeof l.target === "object" ? l.target.id : l.target;
      if (!src || !tgt) continue;
      if (!map.has(src)) map.set(src, new Set());
      if (!map.has(tgt)) map.set(tgt, new Set());
      map.get(src).add(tgt);
      map.get(tgt).add(src);
    }
    return map;
  }, [graphData.links]);

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
  useEffect(() => {
    if (!stageRef.current) return;

    const fg = ForceGraph()(stageRef.current)
      .backgroundColor("rgba(0,0,0,0)")
      .enableNodeDrag(true)
      // 기본 pan 사용(일반적인 '잡고 끌기' 느낌)
      .enablePanInteraction(true)
      // 화면 고정
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

    // [수정] 이전에는 cooldownTicks(100) 때문에 시뮬레이션이 "한 번씩 멈추는" 현상이 있었습니다.
    // 멈추지 않고 계속 자연스럽게 떠다니게 하려면 cooldown을 무한으로 두는 게 안전합니다.
    fg.cooldownTicks(Infinity);
    fg.cooldownTime(Infinity);

    fg.graphData(graphData);

    // 초기 화면 정렬은 size가 잡힌 뒤 별도 effect에서 수행합니다.

    // 노드 간격/안정화(붙어있는 문제 완화)
    // - 반발(charge) 강화
    // - 링크 거리 증가
    // - 감쇠를 낮춰(관성↑) 너무 빨리 복원되는 느낌 완화
    try {
      fg.d3VelocityDecay(0.05);

      const charge = fg.d3Force("charge");
      
      if (charge?.strength) charge.strength(-800); // 노드 간 반발력
      if (charge?.distanceMin) charge.distanceMin(50);
      if (charge?.distanceMax) charge.distanceMax(2000);

      const link = fg.d3Force("link");
      // 링크 거리: 링크마다 고정된 랜덤값(linkDistance)을 사용 (매 프레임 랜덤 금지)
      if (link?.distance) link.distance((l) => l?.linkDistance ?? 160);
      if (link?.strength) link.strength(0.8); // 텐션을 살짝 낮춰서 자연스럽게

      // 충돌 방지 포스 추가 (노드 반지름보다 살짝 크게)
      fg.d3Force("collide", (node) => {
        const r = node.kind === "hub" ? 40 : 25; 
        return r * 1.5; // 여유 공간
      });

    } catch {
      // force 옵션이 환경에 따라 다를 수 있어 방어
    }

    // 링크 스타일은 함수로 등록해 두고(hoverNodeRef 기반), 호버 시에는 "리렌더만" 트리거합니다.
    // 이렇게 하면 hover로 인해 이 effect가 다시 실행되지 않아, 엔진이 다시 '꿈틀'거리지 않습니다.
    fg.linkColor((link) => {
      const hoveredId = hoverNodeRef.current?.id;
      if (!hoveredId) return "rgba(148, 163, 184, 0.18)";
      const src = typeof link.source === "object" ? link.source.id : link.source;
      const tgt = typeof link.target === "object" ? link.target.id : link.target;
      const isAdjacent = src === hoveredId || tgt === hoveredId;
      return isAdjacent ? "rgba(191, 219, 254, 0.28)" : "rgba(148, 163, 184, 0.08)";
    });
    fg.linkWidth((link) => {
      const hoveredId = hoverNodeRef.current?.id;
      if (!hoveredId) return 1;
      const src = typeof link.source === "object" ? link.source.id : link.source;
      const tgt = typeof link.target === "object" ? link.target.id : link.target;
      const isAdjacent = src === hoveredId || tgt === hoveredId;
      return isAdjacent ? 2 : 1;
    });

    fg.onNodeHover((node) => {
      hoverNodeRef.current = node || null;
      setHoverNode(node || null);

      if (containerRef.current) {
        containerRef.current.style.cursor = node ? "pointer" : "default";
      }

      // 호버로 스타일만 바뀌도록 캔버스만 갱신 (엔진 재가열 X)
      fg.refresh?.();
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

        const hoveredId = hoverNodeRef.current?.id;
        const isHovered = hoveredId === node.id;
        const neighborSet = hoveredId ? adjacencyMap.get(hoveredId) : null;
        const isNeighbor = !!neighborSet && neighborSet.has(node.id);
        
        // 노드 크기 조정 (Hub는 크게, Site는 작게)
        const baseR = node.kind === "hub" ? 36 : 14; 
        const r = isHovered ? baseR * 1.4 : isNeighbor ? baseR * 1.2 : baseR;

        if (!isFiniteNumber(r) || r <= 0) return;

        // --- iOS Style Design ---

        // 1. Gradients & Shadows
        const gradient = ctx.createLinearGradient(x - r, y - r, x + r, y + r);

        if (node.kind === "hub") {
          if (isHovered) {
            gradient.addColorStop(0, "#60A5FA"); // Blue-400
            gradient.addColorStop(1, "#2563EB"); // Blue-600
            ctx.shadowColor = "rgba(37, 99, 235, 0.6)"; 
          } else {
            gradient.addColorStop(0, "#93C5FD"); // Blue-300
            gradient.addColorStop(1, "#3B82F6"); // Blue-500
            ctx.shadowColor = "rgba(0, 0, 0, 0.25)"; 
          }
        } else {
          // Site: 깔끔한 화이트/그레이
          if (isHovered) {
            gradient.addColorStop(0, "#FFFFFF");
            gradient.addColorStop(1, "#F1F5F9"); 
            ctx.shadowColor = "rgba(255, 255, 255, 0.5)"; 
          } else {
            gradient.addColorStop(0, "#F8FAFC"); 
            gradient.addColorStop(1, "#E2E8F0"); 
            ctx.shadowColor = "rgba(0, 0, 0, 0.15)";
          }
        }

        ctx.shadowBlur = isHovered ? 20 : 8;
        ctx.shadowOffsetY = isHovered ? 6 : 3;

        // 2. Main Circle
        ctx.beginPath();
        ctx.arc(x, y, r, 0, 2 * Math.PI, false);
        ctx.fillStyle = gradient;
        ctx.fill();

        // 3. Subtle Inner Highlight
        ctx.shadowColor = "transparent"; 
        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;

        const highlightGrad = ctx.createLinearGradient(x, y - r, x, y);
        highlightGrad.addColorStop(0, "rgba(255, 255, 255, 0.4)");
        highlightGrad.addColorStop(0.5, "rgba(255, 255, 255, 0.1)");
        highlightGrad.addColorStop(1, "rgba(255, 255, 255, 0)");

        ctx.beginPath();
        ctx.arc(x, y, r, 0, 2 * Math.PI, false); 
        ctx.fillStyle = highlightGrad;
        ctx.fill();

        // 4. Label (Spacing Improved)
        const label = node.label ?? String(node.id);
        // 폰트는 줌아웃 시 조금 더 작게 보이도록 조정
        const fontSize = clamp(12 / globalScale, 12, 16); 
        
        ctx.font = `600 \${fontSize}px -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Helvetica, Arial, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";

        // 텍스트 스타일: 가독성 확보
        ctx.shadowColor = "rgba(0, 0, 0, 0.6)";
        ctx.shadowBlur = 4;
        ctx.shadowOffsetY = 1;
        ctx.fillStyle = "#FFFFFF";

        // 노드 아래 여백을 줌 레벨에 따라 동적으로 (겹침 방지)
        const textY = y + r + (6 / globalScale);
        ctx.fillText(label, x, textY);

        // Reset
        ctx.shadowColor = "transparent";
        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;
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
  }, [graphData, adjacencyMap, minZoom, maxZoom]);

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
