# 0011: Prefer client cache boundaries before Redis

Status: accepted
Date: 2026-08-27

## Context

The workspace can feel slow when switching among Waveform, Piano Roll, Score, and Spectrogram. It is tempting to treat that as a missing shared server cache and add Redis.

That is not the current bottleneck. A work is loaded into the browser workspace once; representation tab changes only change `activeRepresentation`. Before this decision, `RepresentationStack` rendered one component type at a time, so changing tabs destroyed the previous representation and rebuilt the next one. This is especially expensive for Score because OpenSheetMusicDisplay imports, loads MusicXML, lays out the score, and renders a full SVG when `SheetMusic` mounts.

The application also has a separate server-state concern: `app/page.tsx` manually fetches and refreshes projects, works, work bundles, entities, insights, and job state. Those reads may benefit from an explicit browser query cache, but they do not currently justify another network service.

Redis cache-aside is designed for repeated shared reads where many stateless application instances would otherwise hit the primary database. The current deployment has one API/worker host and relatively low traffic, while most workspace data is user-specific and work-bundle responses contain expiring signed URLs.

## Decision

1. Preserve expensive representation components after their first visit within the active work session. Switching representation tabs is a visibility change rather than a destroy/rebuild cycle.
2. Hidden representation views must suppress high-frequency playhead work where practical. They remain mounted to preserve expensive DOM/library state, but active transport animation is only passed to the visible representation.
3. Do **not** add Redis for frontend tab switching or as a generic modernization dependency.
4. Keep Supabase/Postgres as the durable job and application-data source of truth.
5. Treat a browser server-state cache as the next caching layer to evaluate. TanStack Query is the leading candidate for projects, works, bundles, entities, and insights because it provides query-keyed caching, stale-time policy, invalidation after mutations, and background refresh without adding infrastructure.
6. Do not combine that server-state refactor with this representation-performance change. It should be a separate PR with explicit invalidation semantics for upload, delete, processing completion, retry, variation, and comparison.
7. React 19.2 introduced `<Activity>` for preserving hidden UI/DOM state, and Next.js 16 ships with React 19.2. The repository is currently Next.js 15.5 / React 19.0, so a framework upgrade should be evaluated independently. Once upgraded, revisit whether `<Activity>` can replace the local keep-mounted implementation cleanly.

References:
- React Activity: https://react.dev/reference/react/Activity
- TanStack Query caching: https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults
- Redis cache-aside: https://redis.io/docs/latest/develop/use-cases/cache-aside/
- Next.js 16 / React 19.2: https://nextjs.org/blog/next-16

## Evidence

Current repository behavior:
- `app/page.tsx` loads a work bundle and hydrates representations into the workspace store; tab switches do not invoke `loadWork`.
- `RepresentationStack` previously selected exactly one `ViewComponent`, so every tab switch unmounted the previous representation.
- `SheetMusic` constructs OpenSheetMusicDisplay and renders MusicXML in a mount effect, making repeated Score visits a real client-side rebuild cost.
- durable jobs are already persisted in Postgres and observed through the API; Redis is not required for durability.

External architecture guidance:
- React documents `<Activity>` specifically for hiding/restoring UI and DOM state that is likely to become visible again.
- TanStack Query is designed to cache and synchronize asynchronous server state in React applications.
- Redis documents cache-aside for repeated database reads across application instances, which is a different problem from remounting an already-loaded client visualization.

## Consequences

Positive:
- repeated representation switches avoid rebuilding already-visited expensive views;
- local visualization state can survive switching away and back;
- the app adds no new infrastructure, network hop, or cache invalidation system;
- future caching work has a documented boundary between client visualization state, browser server state, and shared server caching.

Tradeoffs:
- visited representation DOM remains resident until the work changes, increasing browser memory use;
- hidden React wrappers still receive context updates, although high-frequency visual playhead props are gated;
- this does not make first-time Score/Spectrogram rendering faster;
- work-to-work navigation can still refetch data until an explicit browser server-state cache is adopted.

## Revisit when

Reconsider Redis when at least one of these is observed and measured:
- the API is horizontally scaled and rate limits or ephemeral coordination must be shared across instances;
- repeated Supabase reads are a demonstrated backend P95/cost bottleneck after query/index optimization;
- multiple stateless API instances need a common cache with explicit invalidation semantics;
- a new capability genuinely requires Redis primitives such as distributed short-lived counters/locks and Postgres is no longer the simpler fit.

Revisit the representation implementation after a Next.js 16 / React 19.2 upgrade to determine whether React `<Activity>` provides the same state-preservation behavior with better scheduling/effect semantics.
