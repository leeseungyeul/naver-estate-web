/**
 * InfoCards 컴포넌트 테스트 — #9 매물 가치 정보행 (동일주소·사진수·분양권 프리미엄)
 * 실행: npx vitest run src/components/__tests__/InfoCards.test.tsx
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import InfoCards from "../article/InfoCards";
import type { Article } from "@/types";

function makeArticle(overrides: Partial<Article> = {}): Article {
  return {
    article_no: "A001",
    complex_no: "C001",
    trade_type_name: "매매",
    ...overrides,
  };
}

describe("InfoCards — 매물 가치 정보행", () => {
  it("동일주소 매물이 2건 이상이면 가격대와 함께 행 표시", () => {
    render(<InfoCards article={makeArticle({
      same_addr_cnt: 3, same_addr_min_prc: "13억", same_addr_max_prc: "14억",
    })} />);
    expect(screen.getByText("동일주소 매물")).toBeInTheDocument();
    expect(screen.getByText("3건 (13억 ~ 14억)")).toBeInTheDocument();
  });

  it("동일주소 매물이 1건이면 행 미표시 (묶음 아님)", () => {
    render(<InfoCards article={makeArticle({ same_addr_cnt: 1 })} />);
    expect(screen.queryByText("동일주소 매물")).not.toBeInTheDocument();
  });

  it("사진 수가 있으면 '사진 수' 행 표시", () => {
    render(<InfoCards article={makeArticle({ site_image_count: 12 })} />);
    expect(screen.getByText("사진 수")).toBeInTheDocument();
    expect(screen.getByText("12장")).toBeInTheDocument();
  });

  it("분양권 매물이면 프리미엄 행 표시", () => {
    render(<InfoCards article={makeArticle({
      is_presale: true, same_addr_premium_min: "-1000", same_addr_premium_max: "0",
    })} />);
    expect(screen.getByText("분양권 프리미엄")).toBeInTheDocument();
    expect(screen.getByText("-1000 ~ 0")).toBeInTheDocument();
  });

  it("일반 매물(비분양권)은 프리미엄 값이 있어도 행 미표시", () => {
    render(<InfoCards article={makeArticle({
      is_presale: false, same_addr_premium_min: "-1000",
    })} />);
    expect(screen.queryByText("분양권 프리미엄")).not.toBeInTheDocument();
  });
});

describe("InfoCards — #10 매물 상세 정보행", () => {
  it("지하철 도보시간이 있으면 '도보 N분' 행 표시", () => {
    render(<InfoCards article={makeArticle({ walking_time_to_subway: 5 })} />);
    expect(screen.getByText("지하철 도보시간")).toBeInTheDocument();
    expect(screen.getByText("도보 5분")).toBeInTheDocument();
  });

  it("도보시간 0분은 의미 불명확하므로 행 미표시", () => {
    render(<InfoCards article={makeArticle({ walking_time_to_subway: 0 })} />);
    expect(screen.queryByText("지하철 도보시간")).not.toBeInTheDocument();
  });

  it("분양권 유형명이 있으면 '분양권 유형' 행 표시", () => {
    render(<InfoCards article={makeArticle({ isale_right_type_name: "일반분양" })} />);
    expect(screen.getByText("분양권 유형")).toBeInTheDocument();
    expect(screen.getByText("일반분양")).toBeInTheDocument();
  });

  it("일반 매물(분양권 유형명 부재)은 '분양권 유형' 행 미표시", () => {
    render(<InfoCards article={makeArticle()} />);
    expect(screen.queryByText("분양권 유형")).not.toBeInTheDocument();
  });
});

describe("InfoCards — 단지 정보 (세션 429)", () => {
  it("recent_trades_6m 이 있어도 '최근6개월거래' 행 미표시 — 거래 횟수가 아니라 시세 기록 줄 수", () => {
    render(
      <InfoCards
        article={makeArticle()}
        complex={{ complex_no: "C001", complex_name: "테스트단지", recent_trades_6m: 42, jeonse_rate: 60 }}
      />,
    );
    expect(screen.getByText("전세가율")).toBeInTheDocument();
    expect(screen.queryByText("최근6개월거래")).not.toBeInTheDocument();
    expect(screen.queryByText("42건")).not.toBeInTheDocument();
  });
});
