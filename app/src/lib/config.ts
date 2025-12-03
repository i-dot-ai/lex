/**
 * Application configuration
 * Centralized configuration for environment-specific values
 */

export const API_CONFIG = {
  // Proxied URL for API calls (avoids CORS)
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  // Direct backend URL for external links (docs, swagger, etc.)
  backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000',
} as const

export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,
} as const
