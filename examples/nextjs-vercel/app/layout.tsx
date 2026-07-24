export const metadata = {
  title: "Celeris on Next.js",
  description: "Minimal Next.js app calling the Celeris API server-side.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: "3rem auto", maxWidth: 640, padding: "0 1rem" }}>
        {children}
      </body>
    </html>
  );
}
