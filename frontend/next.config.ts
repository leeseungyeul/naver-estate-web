import type { NextConfig } from "next";
import createMDX from "@next/mdx";

const isDev = process.env.NODE_ENV !== "production";

// Vercel 은 배포마다 고유 VERCEL_GIT_COMMIT_SHA / VERCEL_DEPLOYMENT_ID 주입.
// 이를 빌드 ID 로 써서 브라우저가 자기 버전을 알게 한다 (VersionWatcher 가 참조).
const buildId =
  process.env.VERCEL_GIT_COMMIT_SHA ||
  process.env.VERCEL_DEPLOYMENT_ID ||
  process.env.NEXT_PUBLIC_BUILD_ID ||
  `dev-${Date.now()}`;

const nextConfig: NextConfig = {
  // .mdx 파일을 페이지/라우트로 인식. Turbopack·webpack 양쪽 호환 위해 문자열 플러그인.
  pageExtensions: ["ts", "tsx", "md", "mdx"],
  // 개발 서버를 Tailscale IP로 원격 접속할 때 dev 리소스(HMR 폰트 등) 차단 방지
  allowedDevOrigins: ["100.93.169.113"],
  env: {
    NEXT_PUBLIC_BUILD_ID: buildId,
  },
  generateBuildId: async () => buildId,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.naver.net" },
      { protocol: "https", hostname: "**.pstatic.net" },
    ],
    // Next.js 16 default 명시 박제 (4h = 14400s).
    // 우리 이미지 = /public 정적 자산 (블로그 hero, 홈) 위주 + 네이버 단지 사진 외부 URL.
    // 4h cache 가 revalidation 비용·신선도 균형. 외부 URL 자주 갱신 필요 시 60~3600 으로 축소.
    minimumCacheTTL: 14400,
  },
  async redirects() {
    return [
      // 메모 기능 폐기 (세션 132) — 외부 색인 영구 리다이렉트
      { source: "/blog/article-notes-workflow", destination: "/blog", permanent: true },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            // geolocation=(self): 미분양 지도 "내 위치" 표시용 (동일 출처에서만 허용). camera·microphone 은 차단 유지.
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(self)",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              // 네이버 지도 SDK: maps.js 본체(oapi/openapi) + 타일 스타일 JSONP(*.pstatic.net) 가 script 로 로드됨
              // PortOne 결제: npm SDK(@portone/browser-sdk)가 런타임에 cdn.portone.io/v2/browser-sdk.js 동적 로드.
              //   결제창·결제 준비 API 는 PortOne 옛 도메인 *.iamport.co (예: checkout-service.prod.iamport.co) 를 호출하고,
              //   토스 결제수단은 static.tosspayments.com 스크립트를 로드한다 (세션 326 콘솔 차단 로그로 확정).
              //   KPN(한국결제네트웍스) PG 결제창은 *.firstpay.co.kr (testpg.firstpay.co.kr) iframe 으로 뜬다 (세션 326 라이브 확정).
              `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""} https://oapi.map.naver.com https://openapi.map.naver.com https://*.pstatic.net https://vercel.live https://cdn.portone.io https://*.portone.io https://*.iamport.co https://*.tosspayments.com https://*.firstpay.co.kr`,
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob: https://*.naver.net https://*.pstatic.net https://vercel.live https://vercel.com https://*.portone.io https://*.iamport.co https://*.firstpay.co.kr",
              // 네이버 지도 타일 데이터(*.pstatic.net) + 텔레메트리 로그(*.navercorp.com) connect 허용
              // PortOne 결제: SDK 가 결제 준비·상태조회로 *.portone.io + *.iamport.co(checkout-service) API 호출, 토스 결제수단은 *.tosspayments.com, KPN PG 는 *.firstpay.co.kr
              "connect-src 'self' http://localhost:* http://100.93.169.113:8002 https://*.supabase.co https://*.railway.app https://api.2u.pe.kr https://oapi.map.naver.com https://openapi.map.naver.com https://*.pstatic.net https://*.navercorp.com https://vercel.live wss://ws-us3.pusher.com https://*.portone.io https://*.iamport.co https://*.tosspayments.com https://*.firstpay.co.kr",
              // PortOne 결제창·PG사 결제 iframe: portone/iamport + KPN PG(*.firstpay.co.kr). 실 카드결제 시 카드사 도메인이 추가 차단되면 콘솔 로그로 추가 (세션 326 메모)
              "frame-src 'self' https://vercel.live https://*.portone.io https://*.iamport.co https://*.tosspayments.com https://*.firstpay.co.kr",
              "media-src 'self' data:",
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

// Turbopack 호환을 위해 plugin 을 문자열로 전달 (함수 직렬화 불가).
const withMDX = createMDX({
  options: {
    remarkPlugins: [["remark-gfm", {}]],
    rehypePlugins: [],
  },
});

export default withMDX(nextConfig);
