/**
 * Centralized error handling utilities
 */

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }

  if (typeof error === 'string') {
    return error
  }

  return 'An unexpected error occurred'
}

export function isNetworkError(error: unknown): boolean {
  if (error instanceof Error) {
    return error.message.includes('fetch') ||
           error.message.includes('network') ||
           error.message.includes('NetworkError')
  }
  return false
}

export function getApiErrorMessage(error: unknown): string {
  const baseMessage = getErrorMessage(error)

  if (isNetworkError(error)) {
    return `${baseMessage}. Make sure the API is running.`
  }

  return baseMessage
}
