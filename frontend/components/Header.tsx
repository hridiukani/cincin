export default function Header() {
  return (
    <header className="sticky top-0 z-50 h-[57px] flex items-center justify-between px-4 md:px-6 bg-background border-b border-border">
      <span className="text-xl font-bold text-primary tracking-tight">Cincin</span>
      <span className="hidden md:block text-sm text-text-muted">Phoenix deals, found.</span>
    </header>
  );
}
