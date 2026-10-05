"use client";

import { useMemo } from "react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip, Polygon,
} from "recharts";
import type { RadarPoint } from "recharts";
import { COMPARE_COLORS } from "@/lib/constants";
import type { Complex } from "@/types";

const MAX_BUILDING_AGE = 50;

/** 준공년도 → 신축도 (최대 50년, 역수). 준공일이 없거나 해석 불가면 null(빈 값), 50년 넘으면 진짜 0 */
function getNewness(ymd?: string): number | null {
  if (!ymd) return null;
  const year = parseInt(ymd.slice(0, 4), 10);
  if (isNaN(year)) return null;
  const age = new Date().getFullYear() - year;
  return Math.max(0, MAX_BUILDING_AGE - age);
}

interface AxisDef {
  key: string;
  label: string;
  /** 값이 없으면 null — 0점(꼴찌)으로 그리지 않는다 */
  getValue: (c: Complex) => number | null;
  invert?: boolean;
}

const BASE_AXES: AxisDef[] = [
  { key: "household", label: "세대수", getValue: (c) => c.total_household_count ?? null },
  { key: "parking", label: "세대당 주차", getValue: (c) => c.parking_count_by_household ?? null },
  { key: "jeonse", label: "전세가율", getValue: (c) => c.jeonse_rate ?? null },
  { key: "articles", label: "매물수", getValue: (c) => c.article_count ?? null },
  { key: "newness", label: "신축도", getValue: (c) => getNewness(c.use_approve_ymd) },
  { key: "price", label: "주변 시세", getValue: (c) => c.nearby_median_price ?? null },
  { key: "floor", label: "최고층", getValue: (c) => c.high_floor ?? null },
];

export interface RadarMissing {
  complexName: string;
  axes: string[];
}

export interface RadarData {
  /** 축마다 한 줄. 단지 번호 칸 = 0~100 점수, 값이 없으면 null */
  data: Record<string, string | number | null>[];
  /** 종합 우위 단지 이름. 비교 단지 모두 값이 있는 축이 하나도 없으면 "" */
  bestName: string;
  /** 값이 빈 단지와 축 (빈 것이 없는 단지는 빠진다) */
  missing: RadarMissing[];
}

/** 거미줄 그래프 데이터·종합 우위·빈 값 목록 계산 (순수 함수) */
export function buildRadarData(
  complexes: Complex[],
  pricePerPyeong?: Record<string, number>,
): RadarData {
  // 평당가 축 동적 추가
  const axes: AxisDef[] = [...BASE_AXES];
  if (pricePerPyeong && Object.keys(pricePerPyeong).length > 0) {
    axes.push({
      key: "ppyeong",
      label: "평당가",
      getValue: (c) => pricePerPyeong[c.complex_no] ?? null,
      invert: true,
    });
  }

  // 각 축의 max — 값이 있는 단지만으로 (최소 1)
  const maxMap = new Map<string, number>();
  for (const axis of axes) {
    const present = complexes
      .map((c) => axis.getValue(c))
      .filter((v): v is number => v != null);
    maxMap.set(axis.key, Math.max(...present, 1));
  }

  // 정규화 데이터 생성
  const rows = axes.map((axis) => {
    const row: Record<string, string | number | null> = { axis: axis.label };
    const max = maxMap.get(axis.key) ?? 1;
    for (const c of complexes) {
      const raw = axis.getValue(c);
      if (raw == null) {
        row[c.complex_no] = null;
        continue;
      }
      // invert: 낮은 값 = 높은 점수 (평당가)
      row[c.complex_no] = axis.invert
        ? Math.round(((max - raw) / max) * 100)
        : Math.round((raw / max) * 100);
    }
    return row;
  });

  // 종합 우위: 비교 단지 모두 값이 있는 축만 더한다 (빈 값을 0 으로 더하면 꼴찌 취급이 된다)
  const completeRows = rows.filter((r) => complexes.every((c) => r[c.complex_no] != null));
  let bestName = "";
  if (completeRows.length > 0) {
    let bestIdx = 0;
    let bestSum = 0;
    for (let i = 0; i < complexes.length; i++) {
      const sum = completeRows.reduce((acc, r) => acc + Number(r[complexes[i].complex_no]), 0);
      if (sum > bestSum) {
        bestSum = sum;
        bestIdx = i;
      }
    }
    bestName = complexes[bestIdx]?.complex_name ?? "";
  }

  const missing: RadarMissing[] = [];
  for (const c of complexes) {
    const empty = axes.filter((axis) => axis.getValue(c) == null).map((axis) => axis.label);
    if (empty.length > 0) missing.push({ complexName: c.complex_name, axes: empty });
  }

  return { data: rows, bestName, missing };
}

/** 그래프 아래 한 줄: `자료 없음 — 래미안: 전세가율 · 자이: 세대당 주차`. 빈 것이 없으면 null */
export function formatRadarMissing(missing: RadarMissing[]): string | null {
  if (missing.length === 0) return null;
  return `자료 없음 — ${missing.map((m) => `${m.complexName}: ${m.axes.join(", ")}`).join(" · ")}`;
}

interface Props {
  complexes: Complex[];
  pricePerPyeong?: Record<string, number>;
}

export default function CompareRadarChart({ complexes, pricePerPyeong }: Props) {
  const { data, bestName, missing } = useMemo(
    () => buildRadarData(complexes, pricePerPyeong),
    [complexes, pricePerPyeong],
  );

  if (complexes.length < 2) return null;

  const missingLine = formatRadarMissing(missing);

  return (
    <div>
      <ResponsiveContainer width="100%" height={400}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid />
          <PolarAngleAxis dataKey="axis" fontSize={11} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} />
          {complexes.map((c, i) => {
            const color = COMPARE_COLORS[i % COMPARE_COLORS.length].main;
            return (
              <Radar
                key={c.complex_no}
                name={c.complex_name}
                dataKey={c.complex_no}
                stroke={color}
                fill={color}
                fillOpacity={0.15}
                strokeWidth={2}
                // recharts 3 는 null 값을 반지름 0(가운데) 점으로 만든다(polar/Radar.js computeRadarPoints) —
                // connectNulls 로는 못 막으므로 값이 없는 점을 빼고 이웃 축끼리 잇는다
                shape={(p: { points: RadarPoint[] }) => (
                  <Polygon
                    points={p.points.filter((pt) => pt.value != null)}
                    stroke={color}
                    fill={color}
                    fillOpacity={0.15}
                    strokeWidth={2}
                  />
                )}
                activeDot={(p) =>
                  p.value == null ? null : (
                    <circle cx={p.cx} cy={p.cy} r={4} fill={color} stroke="#fff" strokeWidth={2} />
                  )
                }
              />
            );
          })}
          <Legend />
          <Tooltip
            filterNull={false}
            formatter={(v) => (v == null ? "자료 없음" : v)}
          />
        </RadarChart>
      </ResponsiveContainer>
      {bestName && (
        <p className="text-center text-sm mt-2">
          <span className="text-green-600 font-bold">★ 종합 우위: {bestName}</span>
        </p>
      )}
      {missingLine && (
        <p className="text-center text-xs text-muted-foreground mt-1">{missingLine}</p>
      )}
    </div>
  );
}
