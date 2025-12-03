import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const nextConfig: NextConfig = {
  env: {
    // Client-side uses local proxy to avoid CORS
    NEXT_PUBLIC_API_URL: '/api/proxy',
    // Server-side uses direct API URL (no CORS issues)
    API_URL: API_URL,
    // Backend URL for external links (docs, etc.) - not proxied
    NEXT_PUBLIC_BACKEND_URL: API_URL,
  },
  async rewrites() {
    return [
      {
        source: '/api/proxy/:path*',
        destination: `${API_URL}/:path*`,
      },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'www.legislation.gov.uk',
      },
      {
        protocol: 'https',
        hostname: 'caselaw.nationalarchives.gov.uk',
      },
    ],
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https:",
              "font-src 'self' data:",
              `connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'} https://www.legislation.gov.uk https://cloud.langfuse.com`,
              "frame-src 'none'",
            ].join('; '),
          },
        ],
      },
    ]
  },
};

export default nextConfig;
