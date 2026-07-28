import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://rolig.vercel.app"),
  title: "Rolig — Memes matched to your mood",
  description:
    "An open-source, AI-powered meme feed that understands your vibe and gets funnier with every scroll.",
  openGraph: {
    title: "Rolig — Memes matched to your mood",
    description:
      "An open-source, AI-powered meme feed that understands your vibe.",
    images: [
      {
        url: "/og.png",
        width: 1706,
        height: 908,
        alt: "Rolig — memes matched to your mood",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Rolig — Memes matched to your mood",
    description:
      "An open-source, AI-powered meme feed that understands your vibe.",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
