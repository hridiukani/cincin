const FEEDBACK_URL = process.env.NEXT_PUBLIC_FEEDBACK_URL;

export default function Header() {
  return (
    <header className="sticky top-0 z-50 h-[57px] flex items-center justify-between px-4 md:px-6 bg-background border-b border-border">
      <span className="font-display italic text-2xl text-primary tracking-tight">Cincin</span>
      <div className="flex items-center gap-4">
        <span className="hidden md:block text-sm text-text-muted">Phoenix deals, found.</span>
        {FEEDBACK_URL && (
          <a
            href={FEEDBACK_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs md:text-sm font-medium text-primary hover:text-primary-hover transition"
          >
            <span className="hidden md:inline">Report a bug / missing bar</span>
            <span className="md:hidden">Feedback</span>
          </a>
        )}
      </div>
    </header>
  );
}
