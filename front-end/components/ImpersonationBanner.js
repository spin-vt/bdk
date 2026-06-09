import React, { useEffect, useState } from "react";

import { backend_url } from "../utils/settings";

/**
 * Global banner shown when a platform admin is impersonating a user ("logged in
 * as"). The backend tags the app token with an `impersonator` claim, which
 * /api/user surfaces as userinfo.impersonator (the operator's email). The
 * "Return to admin" link hits the admin endpoint that clears the app token and
 * sends the operator back to the admin panel.
 */
export default function ImpersonationBanner() {
  const [impersonator, setImpersonator] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch(`${backend_url}/api/user`, {
          method: "GET",
          credentials: "include",
          headers: { Accept: "application/json" },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && data && data.userinfo && data.userinfo.impersonator) {
          setImpersonator(data.userinfo.impersonator);
        }
      } catch (e) {
        /* not logged in / network error — show nothing */
      }
    }
    check();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!impersonator) return null;

  return (
    <div
      role="alert"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 2000,
        background: "#b8860b",
        color: "#fff",
        padding: "8px 16px",
        display: "flex",
        alignItems: "center",
        gap: "12px",
        fontSize: "14px",
      }}
    >
      <span>
        Impersonating <strong>{impersonator === true ? "a user" : impersonator}</strong>
      </span>
      <a
        href={`${backend_url}/admin/api/impersonate/stop`}
        style={{
          marginLeft: "auto",
          color: "#fff",
          background: "rgba(0,0,0,0.25)",
          padding: "4px 10px",
          borderRadius: "6px",
          textDecoration: "none",
        }}
      >
        Return to admin
      </a>
    </div>
  );
}
