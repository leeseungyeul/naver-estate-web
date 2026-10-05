import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "관심 단지 호가 추적",
  description: "관심 단지·평형의 매매호가를 매일 기록해 같은 집의 호가 변동률과 여러 단지 평균 변동률을 보여드려요",
  robots: { index: false, follow: false },
};

export default function PriceWatchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
