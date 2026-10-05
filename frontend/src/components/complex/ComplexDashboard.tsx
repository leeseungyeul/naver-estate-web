"use client";

import { useState, useRef, useEffect } from "react";
import { Card } from "@/components/ui/card";
import ComplexBasicInfo from "@/components/ComplexBasicInfo";
import { PyeongDetailsList } from "@/components/ComplexPyeongCard";
import ComplexPriceFloorSection from "@/components/complex/ComplexPriceFloorSection";
import ComplexPriceAreaSection from "@/components/complex/ComplexPriceAreaSection";
import PriceChartSection from "@/components/complex/PriceChartSection";
import { useComplexArticleAvg } from "@/hooks/useComplexArticleAvg";
import { formatKoreanPrice } from "@/lib/format";
import type { ArticleFilters, Complex, PyeongDetail } from "@/types";

type SectionKey = "prices" | "chart" | "info" | "area";

interface Props {
  complex: Complex;
  complexNo: string;
  pyeongDetails: PyeongDetail[];
  sessionToken: string | undefined;
  onFilterChange: (filters: ArticleFilters) => void;
}

interface BoxData {
  key: SectionKey;
  label: string;
  primary: string;
  secondary?: string;
}

export default function ComplexDashboard({
  complex,
  complexNo,
  pyeongDetails,
  sessionToken,
  onFilterChange,
}: Props) {
  const [openSection, setOpenSection] = useState<SectionKey | "">("");
  const [isPrinting, setIsPrinting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const { avgPrice, count } = useComplexArticleAvg(complexNo, sessionToken);

  const handleCardClick = (key: SectionKey) => {
    setOpenSection((prev) => (prev === key ? "" : key));
  };

  // 모바일에서만 펼침 영역으로 자동 스크롤. 데스크톱은 viewport 안에 다 보임
  useEffect(() => {
    if (
      openSection &&
      contentRef.current &&
      typeof window !== "undefined" &&
      window.innerWidth < 768
    ) {
      requestAnimationFrame(() => {
        contentRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }, [openSection]);

  // 인쇄 시 4 박스 본문 모두 펼침 (기존 데스크톱 자동 노출 답습, /compare 패턴 답습)
  useEffect(() => {
    const beforePrint = () => setIsPrinting(true);
    const afterPrint = () => setIsPrinting(false);
    window.addEventListener("beforeprint", beforePrint);
    window.addEventListener("afterprint", afterPrint);
    return () => {
      window.removeEventListener("beforeprint", beforePrint);
      window.removeEventListener("afterprint", afterPrint);
    };
  }, []);

  // 박스 라벨·값 계산 (Q3 NULL fallback)
  const boxes: BoxData[] = [
    {
      key: "prices",
      label: "시세",
      primary: complex.nearby_median_price != null
        ? formatKoreanPrice(complex.nearby_median_price)
        : (avgPrice != null ? `매물 평균 ${formatKoreanPrice(avgPrice)}` : "-"),
      secondary: complex.jeonse_rate != null
        ? `전세가율 ${complex.jeonse_rate}%`
        : (count > 0 ? `매물 ${count}건` : undefined),
    },
    {
      key: "chart",
      label: "실거래가",
      // recent_trades_6m 은 실제 거래 횟수가 아니라 시세 기록 줄 수라 "거래 N건"으로 보여 주지 않는다(세션 429)
      primary: `매물 ${count}건`,
      secondary: "현재 매물",
    },
    {
      key: "info",
      label: "단지정보",
      primary: complex.total_household_count != null
        ? `${complex.total_household_count.toLocaleString()}세대`
        : "-",
      secondary: complex.total_dong_count != null ? `${complex.total_dong_count}개동` : undefined,
    },
    {
      key: "area",
      label: "면적별 시세",
      primary: pyeongDetails.length > 0 ? `${pyeongDetails.length}개 평형` : "-",
      secondary: "타입별 / ㎡당",
    },
  ];

  return (
    <div className="space-y-4">
      {/* 바둑판 박스 4개 (모바일 2×2 / 데스크톱 4×1) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3" aria-label="단지 종합 대시보드">
        {boxes.map((b) => (
          <button
            key={b.key}
            type="button"
            onClick={() => handleCardClick(b.key)}
            aria-label={`${b.label} 메뉴 열기`}
            aria-expanded={openSection === b.key}
            aria-controls="dashboard-content"
            className={`flex flex-col items-start rounded-lg border p-3 md:p-4 text-left transition-colors min-h-20 ${
              openSection === b.key
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-gray-400"
            }`}
          >
            <span className="text-[11px] md:text-xs text-gray-500">{b.label}</span>
            <span className="text-sm md:text-base font-semibold mt-0.5 break-keep">{b.primary}</span>
            {b.secondary && <span className="text-[10px] md:text-xs text-gray-400 mt-0.5">{b.secondary}</span>}
          </button>
        ))}
      </div>

      {/* 펼침 영역 (그리드 밖, 가로 전체). 인쇄 시 4 박스 본문 모두 노출 */}
      {(openSection || isPrinting) && (
        <div id="dashboard-content" ref={contentRef} role="region">
          <Card className="p-3 md:p-4 space-y-4">
            {(openSection === "prices" || isPrinting) && (
              <ComplexPriceFloorSection complexNo={complexNo} onFilterChange={onFilterChange} accessToken={sessionToken} />
            )}
            {(openSection === "chart" || isPrinting) && (
              <PriceChartSection complexNo={complexNo} pyeongDetails={pyeongDetails} accessToken={sessionToken} />
            )}
            {(openSection === "info" || isPrinting) && <ComplexBasicInfo cpx={complex} />}
            {(openSection === "area" || isPrinting) && (
              <div className="space-y-3">
                {pyeongDetails.length > 0 ? (
                  <PyeongDetailsList details={pyeongDetails} />
                ) : (
                  <p className="text-gray-500 text-sm">면적별 정보가 아직 수집되지 않았습니다.</p>
                )}
                <ComplexPriceAreaSection complexNo={complexNo} onFilterChange={onFilterChange} accessToken={sessionToken} />
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
