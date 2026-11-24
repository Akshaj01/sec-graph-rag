import type { Metadata } from "next";
import { Atkinson_Hyperlegible, IBM_Plex_Mono, Source_Serif_4 } from "next/font/google";

import { Providers } from "@/components/Providers";
import { SiteHeader } from "@/components/SiteHeader";

import "./globals.css";

const sans = Atkinson_Hyperlegible({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-sans-face",
});

const serif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["400", "600"],
  style: ["normal", "italic"],
  variable: "--font-serif-face",
});

const plex = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-mono-face",
});

export const metadata: Metadata = {
  title: {
    default: "SEC GraphRAG",
    template: "%s · SEC GraphRAG",
  },
  description:
    "Ask a question about a 10-K and follow the route, the graph, and the citations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${serif.variable} ${plex.variable}`}
    >
      <body>
        <Providers>
          <SiteHeader />
          <main className="mx-auto w-full max-w-5xl px-5 py-10">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
