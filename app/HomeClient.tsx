"use client";

import { Suspense } from "react";
import { useAuth } from "@/components/AuthProvider";
import Studio from "@/components/Studio";

const BYPASS_AUTH =
  process.env.NODE_ENV === "development" ||
  process.env.NEXT_PUBLIC_MOCK_ENABLED === "true";

function HomeInner() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="shell" style={{ alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" />
      </div>
    );
  }

  return <Studio signedIn={BYPASS_AUTH || !!user} />;
}

export default function HomeClient() {
  return (
    <Suspense
      fallback={
        <div className="shell" style={{ alignItems: "center", justifyContent: "center" }}>
          <div className="spinner" />
        </div>
      }
    >
      <HomeInner />
    </Suspense>
  );
}
