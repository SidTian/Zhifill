export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export async function getHealth(): Promise<{ status: string; phase?: string }> {
  const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`health failed: ${res.status}`);
  }
  return res.json();
}
