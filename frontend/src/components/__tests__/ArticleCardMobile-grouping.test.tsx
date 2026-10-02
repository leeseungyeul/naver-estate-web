import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ArticleCardMobile from "../ArticleCardMobile";
import type { Article } from "@/types";

const a1: Article = { article_no: "A1", complex_no: "C", trade_type_name: "매매", building_name: "101동", deal_or_warrant_prc: "12억", realtor_name: "가중개" };
const a2: Article = { ...a1, article_no: "A2", realtor_name: "나중개" };

describe("mobile grouped listing", () => {
  it("expands members in compact mode and opens a member detail", () => {
    const onClick = vi.fn();
    render(<ArticleCardMobile articles={[{ ...a1, group_count: 2, group_members: [a1, a2] }]}
      viewMode="compact" onRowClick={onClick} />);
    fireEvent.click(screen.getByRole("button", { name: "추정 묶음 2건 펼치기" }));
    expect(onClick).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /원본 매물 A2/ }));
    expect(onClick).toHaveBeenCalledWith("A2");
  });
});
