"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import Studio from "@/components/Studio";

const BYPASS_AUTH =
  process.env.NODE_ENV === "development" ||
  process.env.NEXT_PUBLIC_MOCK_ENABLED === "true";

function HomeInner() {
  const { user, loading } = useAuth();
  const params = useSearchParams();
  const tab = params.get("tab") || undefined;
  const track = params.get("track") || undefined;

  if (loading) {
    return (
      <div className="page" style={{ alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" />
      </div>
    );
  }

  return <Studio initialTab={tab} initialTrack={track} signedIn={BYPASS_AUTH || !!user} />;
}

export default function HomeClient() {
  return (
    <Suspense
      fallback={
        <div className="page" style={{ alignItems: "center", justifyContent: "center" }}>
          <div className="spinner" />
        </div>
      }
    >
      <HomeInner />
    </Suspense>
  );
}
