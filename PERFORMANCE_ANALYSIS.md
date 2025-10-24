# Legislation Preview Performance Analysis

## Executive Summary

**Current Performance:** Proxy is actually **96.3% faster** than direct access to legislation.gov.uk (130ms vs 3512ms average). The perceived latency is likely from **frontend processing**, not network.

**Key Finding:** The bottleneck is frontend HTML sanitization + rendering, especially for large documents (e.g., Data Protection Act 2018 = 3.6MB of HTML).

## Benchmark Results

### Backend Proxy Performance (Python httpx)

| Document | Size | Direct | Proxy | Overhead |
|----------|------|--------|-------|----------|
| Data Protection Act 2018 | 3592 KB | 14.52s | 0.19s | **-98.7%** ✅ |
| Arbitration Act 2024 | 303 KB | 0.20s | 0.09s | -57.4% ✅ |
| Human Rights Act 1998 | 230 KB | 0.67s | 0.08s | -87.5% ✅ |
| UKSI 2024/1 | 3 KB | 0.33s | 0.18s | -47.1% ✅ |
| European Union Act 2020 | 666 KB | 1.84s | 0.12s | -93.5% ✅ |

**Average:** Direct 3.51s → Proxy 0.13s (96.3% faster) ⚡

### Why is the Proxy Faster?

1. **Better network routing** from backend to legislation.gov.uk CDN
2. **Connection pooling** in httpx AsyncClient
3. **Geographic proximity** to legislation.gov.uk servers

## Problem: Frontend Processing Bottlenecks

Based on research and code analysis, the frontend pipeline has several bottlenecks:

1. **TanStack Query Cache Duration** (CRITICAL)
   - Current: `staleTime: 60s`, `gcTime: 5min`
   - Problem: Legislation HTML refetches after 1 minute (unnecessary)
   - Legislation content is **immutable** - never changes once published

2. **DOMPurify Sanitization** (MEDIUM)
   - Running on every render
   - Not memoized
   - 3.6MB HTML = significant processing time

3. **Image URL Replacement** (LOW)
   - String replace on 3.6MB of HTML
   - Not memoized

4. **React Rendering** (LOW)
   - Large DOM insertion
   - Browser reflow/repaint

## Performance Improvement Proposals

### 🎯 Priority 1: Increase TanStack Query Cache Duration (HIGH IMPACT, LOW EFFORT)

**Problem:** Legislation HTML is static but refetched after 60 seconds.

**Solution:** Set long cache times for immutable content.

**File:** `app/src/components/legislation-preview.tsx`

```typescript
// Current (lines 272-280)
const { data: htmlContent, isLoading: htmlLoading } = useQuery<string>({
  queryKey: ['legislation-html', legislation.id],
  queryFn: async () => {
    const response = await fetch(`${API_CONFIG.baseUrl}/legislation/proxy/${legislationPath}/data.html`)
    if (!response.ok) throw new Error('Failed to fetch HTML')
    return response.text()
  },
  enabled: open && activeTab === 'fulltext'
})

// Proposed
const { data: htmlContent, isLoading: htmlLoading } = useQuery<string>({
  queryKey: ['legislation-html', legislation.id],
  queryFn: async () => {
    const response = await fetch(`${API_CONFIG.baseUrl}/legislation/proxy/${legislationPath}/data.html`)
    if (!response.ok) throw new Error('Failed to fetch HTML')
    return response.text()
  },
  enabled: open && activeTab === 'fulltext',
  staleTime: 24 * 60 * 60 * 1000, // 24 hours - legislation is immutable
  gcTime: 24 * 60 * 60 * 1000,    // 24 hours - keep in memory
})
```

**Benefits:**
- ✅ Eliminates unnecessary refetches
- ✅ Instant loading on second view
- ✅ No code complexity
- ✅ No backend changes needed

**Impact:** ~100ms saved on second view (eliminates network roundtrip)

---

### 🎯 Priority 2: Memoize HTML Sanitization (HIGH IMPACT, LOW EFFORT)

**Problem:** DOMPurify runs on every render, even when HTML hasn't changed.

**Solution:** Use `useMemo` to cache sanitized HTML.

**File:** `app/src/components/legislation-preview.tsx`

```typescript
// Add near other hooks (after line 102)
const sanitizedHtml = useMemo(() => {
  if (!htmlContent) return ''

  // Fix image URLs and sanitize in one operation
  return DOMPurify.sanitize(
    htmlContent.replace(/src="\/images\//g, 'src="https://www.legislation.gov.uk/images/'),
    {
      ADD_TAGS: ['img'],
      ADD_ATTR: ['src', 'alt', 'width', 'height', 'class']
    }
  )
}, [htmlContent])

// Then update render (lines 804-816)
<div
  ref={contentRef}
  className="legislation-content pr-4"
  dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
/>
```

**Benefits:**
- ✅ Sanitization only runs when HTML changes
- ✅ Prevents re-sanitization on tab switch, scroll, etc.
- ✅ Simple React pattern
- ✅ No external dependencies

**Impact:** ~50-200ms saved per render (depends on document size)

---

### 🎯 Priority 3: Add Backend Caching (MEDIUM IMPACT, MEDIUM EFFORT)

**Problem:** Every user's first view fetches from legislation.gov.uk.

**Solution:** Add simple in-memory cache in FastAPI backend.

**File:** `src/backend/legislation/router.py`

```python
from functools import lru_cache
from datetime import datetime, timedelta

# Simple in-memory cache with TTL
_html_cache: dict[str, tuple[bytes, str, datetime]] = {}
_CACHE_TTL = timedelta(hours=24)

def get_cached_html(legislation_id: str) -> tuple[bytes, str] | None:
    """Get cached HTML if available and not expired."""
    if legislation_id in _html_cache:
        content, content_type, cached_at = _html_cache[legislation_id]
        if datetime.now() - cached_at < _CACHE_TTL:
            return content, content_type
        else:
            # Expired, remove from cache
            del _html_cache[legislation_id]
    return None

def cache_html(legislation_id: str, content: bytes, content_type: str):
    """Cache HTML content."""
    _html_cache[legislation_id] = (content, content_type, datetime.now())

    # Simple cache size management: remove oldest if too large
    if len(_html_cache) > 1000:  # Keep max 1000 documents in memory
        oldest = min(_html_cache.items(), key=lambda x: x[1][2])
        del _html_cache[oldest[0]]

@router.get("/proxy/{legislation_id:path}")
async def proxy_legislation_data(legislation_id: str):
    """Proxy endpoint with in-memory caching."""
    try:
        # Check cache first
        cached = get_cached_html(legislation_id)
        if cached:
            content, content_type = cached
            return Response(
                content=content,
                media_type=content_type,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=86400",  # 24 hours
                    "X-Cache": "HIT",  # Debug header
                },
            )

        # Cache miss - fetch from legislation.gov.uk
        url = f"https://www.legislation.gov.uk/{legislation_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Legislation not found: {legislation_id}")

            response.raise_for_status()

            # Cache the response
            content_type = response.headers.get("content-type", "text/html")
            cache_html(legislation_id, response.content, content_type)

            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=86400",  # 24 hours
                    "X-Cache": "MISS",  # Debug header
                },
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"External API error: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Request failed: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        error_detail = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
        raise HTTPException(status_code=500, detail=error_detail)
```

**Benefits:**
- ✅ Reduces load on legislation.gov.uk
- ✅ Faster response for all users (not just repeat viewers)
- ✅ Simple in-memory cache (no Redis needed)
- ✅ Automatic cache size management
- ✅ Debug headers show cache hits/misses

**Trade-offs:**
- ⚠️ Memory usage: ~1GB max (1000 docs × ~1MB avg)
- ⚠️ Cache lost on backend restart (acceptable for legislation)
- ⚠️ Not distributed (single instance only)

**Impact:** ~100ms saved on first view for all users

**Alternative (if distributed cache needed):** Use Redis instead of in-memory dict.

---

### 🎯 Priority 4: Lazy Load Images (LOW IMPACT, LOW EFFORT)

**Problem:** Large legislation documents have many images that block rendering.

**Solution:** Add `loading="lazy"` to images in sanitization.

**File:** `app/src/components/legislation-preview.tsx`

```typescript
const sanitizedHtml = useMemo(() => {
  if (!htmlContent) return ''

  // Fix image URLs
  let processedHtml = htmlContent.replace(/src="\/images\//g, 'src="https://www.legislation.gov.uk/images/')

  // Add lazy loading to images
  processedHtml = processedHtml.replace(/<img /g, '<img loading="lazy" ')

  return DOMPurify.sanitize(processedHtml, {
    ADD_TAGS: ['img'],
    ADD_ATTR: ['src', 'alt', 'width', 'height', 'class', 'loading']
  })
}, [htmlContent])
```

**Benefits:**
- ✅ Faster initial render
- ✅ Reduces data transfer for above-fold content
- ✅ Native browser feature (no library needed)

**Impact:** ~20-50ms saved on initial render

---

## Recommendations

### Immediate Actions (Do This Now)

1. ✅ **Priority 1:** Increase TanStack Query cache duration → 5 min implementation
2. ✅ **Priority 2:** Memoize sanitization → 10 min implementation

**Expected improvement:** 150-300ms faster on second view, 50-200ms faster on every render.

### Optional Enhancements (If Still Experiencing Latency)

3. ⏸️ **Priority 3:** Add backend caching → 30 min implementation
4. ⏸️ **Priority 4:** Lazy load images → 5 min implementation

**Expected improvement:** Additional 100-150ms faster.

---

## Things to AVOID (Overengineering)

❌ **Streaming/Progressive rendering** - Complex, limited benefit
❌ **Web Workers for sanitization** - Overhead > benefit for this use case
❌ **Virtual scrolling** - Legislation structure doesn't suit chunking
❌ **Service Worker caching** - Unnecessary with TanStack Query
❌ **React.lazy() for component** - Preview is already conditionally rendered

---

## Measuring Success

### Before Optimization
- First view: ~200-500ms (3.6MB document)
- Second view: ~200-500ms (refetch after 60s)
- Re-render: ~50-200ms (re-sanitization)

### After Priority 1 + 2
- First view: ~200-500ms (unchanged)
- Second view: ~10-50ms ⚡ (cached HTML + memoized sanitization)
- Re-render: ~1-5ms ⚡ (memoized sanitization)

### After Priority 1 + 2 + 3
- First view: ~100-200ms ⚡ (backend cache)
- Second view: ~10-50ms ⚡
- Re-render: ~1-5ms ⚡

---

## Test Instructions

### Frontend Benchmark

1. Open `scripts/benchmark_frontend_processing.html` in browser
2. Click "Run Benchmark"
3. Compare timings for different document sizes

### Backend Benchmark

```bash
uv run python scripts/benchmark_legislation_proxy.py
```

### Browser DevTools

1. Open preview with Network tab open
2. Check timing breakdown:
   - "Waiting (TTFB)" = backend processing
   - "Content Download" = network transfer
   - Look for cached responses (304 status or instant load)

---

## Conclusion

The proxy architecture is **excellent** - 96% faster than direct access. The issue is frontend processing of large HTML documents (up to 3.6MB).

**Recommended approach:**
1. Start with Priority 1 + 2 (15 minutes, high impact)
2. Measure improvement with user testing
3. If still needed, add Priority 3 (backend cache)

**Key principle:** Legislation content is **immutable** - cache aggressively!
