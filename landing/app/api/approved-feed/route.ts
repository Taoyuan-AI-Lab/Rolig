import { NextResponse } from "next/server";

const backendFeedUrl =
  "https://rolig-backend.onrender.com/api/v1/feed?limit=100";

export const revalidate = 300;

export async function GET() {
  try {
    const response = await fetch(backendFeedUrl, {
      headers: { Accept: "application/json" },
      next: { revalidate },
    });

    if (!response.ok) {
      throw new Error(`Approved feed returned ${response.status}`);
    }

    const feed = (await response.json()) as { items?: unknown[] };

    return NextResponse.json(
      { items: Array.isArray(feed.items) ? feed.items : [] },
      {
        headers: {
          "Cache-Control":
            "public, s-maxage=300, stale-while-revalidate=86400",
        },
      },
    );
  } catch {
    return NextResponse.json(
      { items: [], error: "Approved feed is temporarily unavailable." },
      { status: 502 },
    );
  }
}
