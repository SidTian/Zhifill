import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "智填 ZhiFill",
  description: "个人知识图谱自动填表 — 前端演示",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <nav>
          <Link className="brand" href="/">
            智填 ZhiFill
          </Link>
          <span className="mock-pill">演示版</span>
          <Link href="/knowledge">知识库</Link>
          <Link href="/forms">填表</Link>
          <Link href="/settings">设置</Link>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
