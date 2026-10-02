"""네이버 그룹 모드(sameAddressGroup=true) 별도 수집 — 원본 매물에 sameAddrCnt 덮어쓰기.

네이버가 실제로 묶은 대표 행의 sameAddrCnt 를 DB 원본 매물에 기록한다(선택지 a).
개별 수집(crawl_articles_batch)은 유지 — 삭제·비활성 판정은 개별 모드가 담당하고,
그룹 수집은 sameAddrCnt 갱신만 하므로 원본 손실 위험이 없다.

실측(2026-10-02, 개봉아이파크 17538): 개별 143건 / 그룹 33그룹.
"""
import logging

from sqlalchemy.orm import Session

from db.models import Article
from shared.naver_api import NaverEstateAPI

logger = logging.getLogger(__name__)


def update_same_addr_counts_from_naver(db: Session, complex_no: str) -> dict:
    """그룹 모드로 네이버를 읽어 (동·층·가격·방향이 같은) 원본 등록에 sameAddrCnt 를 기록.

    매칭 기준: building_name + dealOrWarrantPrc 문자열 + trade_type_name.
    네이버 대표 행의 표시 특징이 곧 묶음의 공통 특징이므로 이 키로 원본을 찾는다.
    같은 키 원본이 여럿이면 모두 같은 묶음 수를 받는다(대표 1행이 대표하는 등록들).
    반환: {"groups": 읽은 그룹 수, "matched": 갱신된 원본 행 수, "unmatched": 못 찾은 그룹 수}
    """
    page, groups, matched, unmatched = 1, 0, 0, 0
    while True:
        result = NaverEstateAPI.get_complex_articles(complex_no, page=page, same_address_group=True)
        article_list = (result or {}).get("articleList") or []
        if not article_list:
            break
        for a in article_list:
            groups += 1
            if not isinstance(a, dict):
                continue
            cnt = a.get("sameAddrCnt")
            if cnt is None or cnt < 1:
                continue
            # 매칭 우선순위(실측 반영): (동,가격,거래,층,면적) 정확 일치가 최우선.
            # 같은 동·가격이라도 네이버는 층 미상('중/18') 대표와 정확 층('4/18') 대표를
            # 별도로 내려주고, 정확 층 대표가 더 큰 sameAddrCnt(26)를 갖는다.
            # 따라서 정확 일치가 없을 때만 층-미상 대표로 폴백해 원본 전체를 커버한다.
            area2 = a.get("area2")
            base = [
                Article.complex_no == complex_no,
                Article.is_active.is_(True),
                Article.building_name == a.get("buildingName"),
                Article.deal_or_warrant_prc == a.get("dealOrWarrantPrc"),
                Article.trade_type_name == a.get("tradeTypeName"),
            ]
            rows = db.query(Article).filter(
                *base, Article.floor_info == a.get("floorInfo"), Article.area2_m2 == area2,
            ).all()
            fi = a.get("floorInfo") or ""
            if not rows and "/" in fi and not fi.split("/")[0].isdigit():
                # 층 미상 대표(중/18·저/18 등): 정확한 층 원본 + 다른 층-미상 원본 모두 커버
                exact_dong_prc = db.query(Article).filter(
                    *base, Article.area2_m2 == area2,
                ).all()
                rows = exact_dong_prc
            if rows:
                for row in rows:
                    # 같은 호실의 중개사 다수 등록이 대표 여러 건으로 옴(실측: cnt 26과 1이
                    # 동일 키로 공존) — 같은 키 대표 중 최댓값만 남긴다(뒤 행이 덮지 않게).
                    if row.same_addr_cnt is None or cnt > row.same_addr_cnt:
                        row.same_addr_cnt = cnt
                matched += len(rows)
            else:
                unmatched += 1
        if not result.get("isMoreData", False):
            break
        page += 1
        if page > 40:
            logger.warning("그룹 수집 40페이지 초과 중단: complex %s", complex_no)
            break
    db.commit()
    return {"groups": groups, "matched": matched, "unmatched": unmatched}
