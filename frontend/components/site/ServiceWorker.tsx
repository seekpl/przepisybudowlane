"use client";

import { useEffect } from "react";

/** Rejestruje service worker PWA (tylko w produkcji — w trybie deweloperskim przeszkadzałby w odświeżaniu). */
export function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* PWA jest dodatkiem — aplikacja działa także bez service workera */
    });
  }, []);
  return null;
}
