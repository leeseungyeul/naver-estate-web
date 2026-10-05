/**
 * 관리자 "외부 자료 지금 받아오기" 버튼 8종의 정본 (사장님 결정 2026-09-26).
 *
 * - name        : BE 가 받는 수집기 이름 (backend/routers/admin/collect.py `CollectorName` — 집합 일치는
 *                 src/lib/admin/__tests__/collectors.test.ts 가 그 파일을 읽어 대조한다)
 * - jobType     : 그 수집기가 남기는 crawl_jobs.job_type — 버튼 이름은 이 값의 한글 이름표(crawl-job-labels.ts,
 *                 BE plain_words.JOB_WORDS 와 같은 표현)를 그대로 쓴다. 이름을 여기 손으로 또 적지 않는다.
 *                 짝꿍 = backend/routers/admin/collect.py `_COLLECTOR_JOB_TYPE`(중복 실행 409 판정에 쓰인다) —
 *                 한쪽을 바꾸면 양쪽을 같이 바꾼다. 짝 단위 대조 = backend/tests/test_admin_collect_background.py
 * - schedulerJobId : 마지막 실행·결과를 읽어 올 scheduler-status 의 잡 id (crawler/scheduler.py)
 * - extraSchedulerJobIds : 같은 버튼이 여러 예약 잡의 결과를 함께 보는 경우(예: 관리비 06:20/12:40
 *                 두 회차) 그 나머지 잡 id. 있으면 여러 잡의 last_run 중 더 늦게 시작한 것을 보여주고,
 *                 머리말 뒤에 "(HH:MM 시작)" 을 붙여 어느 회차인지 밝힌다(세션 423).
 * - manualCounted  : 이 버튼으로 돌린 실행도 그 잡 id 로 기록되는가.
 *                 false 인 둘(backfill-price·metrics)은 BE 가 수동 실행에 잡 id 를 붙이지 않아
 *                 scheduler-status 에는 자동 실행만 보인다 → 화면에 "마지막 자동 실행" 이라고 적는다.
 * - long        : 한 번 돌면 오래 걸리는 것 — 누르기 전에 confirm 으로 시간·호출 수를 묻는다.
 *                 (세션 420 부터 API 는 모든 수집기를 백그라운드로 시작하고 곧바로 답한다 — 기다리는 시간은 같다.)
 * - confirm     : 누르기 전에 묻는 문장. 시간·호출 수는 .claude/rules/infra.md 표와 backend/.claude/details.md 의 실측값.
 */
import type { SchedulerLastRun } from "@/types/admin";
import { formatRelativeKo } from "@/lib/format-relative";

export type CollectorName =
  | "crime-stats"
  | "air-quality"
  | "emergency"
  | "childcare"
  | "backfill-price"
  | "metrics"
  | "kapt-match"
  | "kapt-costs";

export interface CollectorDef {
  name: CollectorName;
  jobType: string;
  schedulerJobId: string;
  /** 같은 버튼이 함께 보는 다른 예약 잡 id (세션 423 — 관리비 06:20/12:40 두 회차) */
  extraSchedulerJobIds?: string[];
  manualCounted: boolean;
  description: string;
  long: boolean;
  confirm?: string;
}

export const COLLECTORS: readonly CollectorDef[] = [
  {
    name: "crime-stats",
    jobType: "crime_stats",
    schedulerJobId: "collect_crime_stats",
    manualCounted: true,
    description: "경찰청 시군구별 범죄 통계를 새로 받아요",
    long: false,
  },
  {
    name: "air-quality",
    jobType: "air_quality",
    schedulerJobId: "collect_air_quality",
    manualCounted: true,
    description: "미세먼지를 한동안 못 받은 단지 100곳부터 새로 받아요",
    long: false,
  },
  {
    name: "emergency",
    jobType: "emergency",
    schedulerJobId: "collect_emergency",
    manualCounted: true,
    description: "전국 응급실 목록을 받아 단지마다 가까운 곳을 다시 찾아요",
    long: false,
  },
  {
    name: "childcare",
    jobType: "childcare",
    schedulerJobId: "collect_childcare",
    manualCounted: true,
    description: "전국 어린이집 정원·교사 정보를 받아 단지마다 다시 붙여요",
    long: true,
    confirm:
      "지금 시작하면 약 20~30분(예상) 걸리고 어린이집 자료 호출을 약 250회 써요. " +
      "이 창구는 미분양 서비스와 하루 1,000회를 나눠 쓰는데, 새벽 4시 30분 이후엔 그쪽이 한도를 다 써서 실패할 수 있어요. 계속할까요?",
  },
  {
    name: "backfill-price",
    jobType: "price_backfill",
    schedulerJobId: "backfill_price",
    manualCounted: false,
    description: "시세 기록이 적은 큰 단지 20곳을 골라 지난 2년 실거래가를 채워요",
    long: true,
    confirm:
      "지금 시작하면 보통 몇 분, 자료가 많으면 한 시간 넘게 걸리고 공공데이터 호출을 최대 약 480회 써요 " +
      "(하루 1만 회를 미분양 서비스와 나눠 써요). 계속할까요?",
  },
  {
    name: "metrics",
    jobType: "complex_metric",
    schedulerJobId: "collect_metrics",
    manualCounted: false,
    description: "최근 6개월 매매가 있는 모든 단지의 가치 점수를 다시 계산해요 (외부 호출 없음)",
    long: false,
  },
  {
    name: "kapt-match",
    jobType: "kapt_match",
    schedulerJobId: "kapt_match",
    manualCounted: true,
    description: "관리비 사이트(K-apt)의 전국 단지 목록과 우리 단지를 다시 짝지어요",
    long: true,
    confirm:
      "지금 시작하면 약 6시간 걸리고 관리비 자료 호출을 약 1만 5천 회 써요. " +
      "짝이 바뀐 단지는 옛 연결과 관리비 기록이 정리돼요. " +
      "그동안(약 6시간) 관리비 받기는 쉬어요. 계속할까요?",
  },
  {
    name: "kapt-costs",
    jobType: "kapt_costs",
    schedulerJobId: "kapt_costs",
    extraSchedulerJobIds: ["kapt_costs_noon", "kapt_costs_evening"],
    manualCounted: true,
    description: "짝지어진 단지 중 새 달이 나온 곳의 관리비를 받아요(한 번에 약 200곳)",
    long: true,
    confirm:
      "지금 시작하면 보통 약 2시간, 길면 2시간 반 걸리고 관리비 자료 호출을 약 4,800회 써요 (우리 하루 상한 6만 회). 계속할까요?",
  },
];

export type LastRunTone = "ok" | "fail" | "running" | "none";

export interface LastRunSummary {
  /** 버튼 아래 한 줄 */
  text: string;
  tone: LastRunTone;
  /** 지금 도는 중 — 버튼을 막는다 */
  running: boolean;
  /** 실패 원문 (마우스 올리면 보이게) */
  raw?: string;
}

/**
 * 여러 예약 잡의 마지막 실행 중 실제로 더 늦게 시작한 것을 고른다(세션 423 — 관리비 06:20/12:40).
 * null/undefined 는 무시. started_at 을 못 읽으면(Date.parse 실패) 그 실행은 가장 옛것으로 친다.
 * 시각이 같거나 전부 못 읽으면 앞쪽(배열 순서상 먼저 온 것 = schedulerJobId)을 쓴다.
 */
export function pickLatestRun(
  runs: Array<SchedulerLastRun | null | undefined>,
): SchedulerLastRun | null {
  let best: SchedulerLastRun | null = null;
  let bestTime = -Infinity;
  for (const run of runs) {
    if (!run) continue;
    const t = run.started_at ? Date.parse(run.started_at) : NaN;
    const time = Number.isNaN(t) ? -Infinity : t;
    if (!best || time > bestTime) {
      best = run;
      bestTime = time;
    }
  }
  return best;
}

/** 한국 시각 "HH:MM" — RunningJobsLine.tsx startedText 와 같은 옵션(영문 AM/PM 회피) */
function startClockKo(iso?: string): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("ko", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "Asia/Seoul" });
}

/**
 * scheduler-status 의 마지막 실행 → 버튼 아래 한 줄.
 * showStartClock 이 참이고 시작 시각을 읽을 수 있을 때만 머리말·"도는 중" 문구 뒤에
 * "(HH:MM 시작)" 을 붙인다 — 잡 id 를 여러 개 보는 카드(관리비)에서 어느 회차인지 밝히기 위함.
 */
export function describeLastRun(
  lastRun: SchedulerLastRun | null | undefined,
  manualCounted: boolean,
  now: Date = new Date(),
  showStartClock: boolean = false,
): LastRunSummary {
  const baseHead = manualCounted ? "마지막 실행" : "마지막 자동 실행";
  if (!lastRun) return { text: `${baseHead}: 기록 없음`, tone: "none", running: false };
  const clock = showStartClock ? startClockKo(lastRun.started_at) : null;
  const head = clock ? `${baseHead}(${clock} 시작)` : baseHead;
  const startedRel = formatRelativeKo(lastRun.started_at, now);
  const endRel = formatRelativeKo(lastRun.completed_at ?? lastRun.started_at, now);
  switch (lastRun.status) {
    case "running":
    case "pending": {
      const runningClock = clock ? ` (${clock} 시작)` : ` (${startedRel} 시작)`;
      return { text: `지금 도는 중${runningClock}`, tone: "running", running: true };
    }
    case "completed": {
      const total = lastRun.total_items ?? 0;
      const done = lastRun.processed_items ?? 0;
      const count = total > 0 ? ` (${done.toLocaleString("ko-KR")}/${total.toLocaleString("ko-KR")}건)` : "";
      return { text: `${head}: ${endRel} · 완료${count}`, tone: "ok", running: false };
    }
    case "failed": {
      const reason = lastRun.error_plain || (lastRun.error_message ? "사유는 아래 '수집 작업 목록'에서 보세요" : "");
      return {
        text: `${head}: ${endRel} 실패${reason ? ` — ${reason}` : ""}`,
        tone: "fail",
        running: false,
        raw: lastRun.error_message ?? undefined,
      };
    }
    case "cancelled":
      return { text: `${head}: ${endRel} · 취소됨`, tone: "none", running: false };
    case "paused":
      return { text: `${head}: ${startedRel} 시작 · 일시정지`, tone: "none", running: false };
    default:
      return { text: `${head}: ${endRel}`, tone: "none", running: false };
  }
}
