"use client";

import { useState } from "react";
import Link from "next/link";
import { useArticleFavorites } from "@/hooks/useArticleFavorites";
import ArticleFavoritesTab from "@/components/ArticleFavoritesTab";
import ArticleDetail from "@/components/ArticleDetail";

/**
 * 매물 즐겨찾기 모아보기 — favorite_articles(localStorage) 한곳 보기.
 * 단지 즐겨찾기는 홈에 칩으로 노출되나 매물은 모아보기가 없던 비대칭 해소(세션 294).
 * 행 클릭 시 ArticleDetail 모달(articleNo 단독 → getArticleLive 최신 재조회, 단지 정보는 미표시 수용).
 */
export default function ArticleFavoritesPage() {
  const { favorites, toggle } = useArticleFavorites();
  const [selectedArticle, setSelectedArticle] = useState<string | null>(null);
  // 삭제된 매물(404) 안내의 '즐겨찾기에서 제거' CTA 용 — toggle 이 내부 refresh 로 목록도 즉시 갱신
  const selectedFav = selectedArticle
    ? favorites.find((f) => f.article_no === selectedArticle)
    : undefined;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-gray-900">즐겨찾기 매물</h1>
        <div className="flex items-center gap-3">
          <Link href="/price-watch" className="text-sm text-blue-600 hover:underline">
            관심 단지 호가 추적
          </Link>
          <Link href="/search" className="text-sm text-blue-600 hover:underline">
            &#8592; 검색으로
          </Link>
        </div>
      </div>

      <ArticleFavoritesTab
        favorites={favorites}
        onRowClick={setSelectedArticle}
        onRemove={toggle}
      />

      {selectedArticle && (
        <ArticleDetail
          articleNo={selectedArticle}
          onClose={() => setSelectedArticle(null)}
          onRemoveFavorite={
            selectedFav
              ? () => {
                  toggle(selectedFav);
                  setSelectedArticle(null);
                }
              : undefined
          }
        />
      )}
    </div>
  );
}
