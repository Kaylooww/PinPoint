// Figma "Logo" (3:158). The mark's paths come from the Figma asset; the stroke uses
// currentColor so it follows the --accent token in both themes.
export function Logo({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg
        width="22"
        height="22"
        viewBox="0 0 22 22"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="shrink-0 text-accent"
        aria-hidden="true"
      >
        <path d="M12.8333 1.83333H5.5C5.01377 1.83333 4.54745 2.02649 4.20364 2.3703C3.85982 2.71412 3.66667 3.18044 3.66667 3.66667V18.3333C3.66667 18.8196 3.85982 19.2859 4.20364 19.6297C4.54745 19.9735 5.01377 20.1667 5.5 20.1667H16.5C16.9862 20.1667 17.4525 19.9735 17.7964 19.6297C18.1402 19.2859 18.3333 18.8196 18.3333 18.3333V7.33333L12.8333 1.83333Z" />
        <path d="M12.8333 1.83333V7.33333H18.3333" />
        <path d="M11 16.5C11 16.5 8.25 14.1167 8.25 11.9167C8.25 11.1873 8.53973 10.4878 9.05546 9.97212C9.57118 9.4564 10.2707 9.16667 11 9.16667C11.7293 9.16667 12.4288 9.4564 12.9445 9.97212C13.4603 10.4878 13.75 11.1873 13.75 11.9167C13.75 14.1167 11 16.5 11 16.5Z" />
        <path d="M11.9167 11.9167C11.9167 12.4229 11.5063 12.8333 11 12.8333C10.4937 12.8333 10.0833 12.4229 10.0833 11.9167C10.0833 11.4104 10.4937 11 11 11C11.5063 11 11.9167 11.4104 11.9167 11.9167Z" />
      </svg>
      <span className="text-h3 text-text">PinPoint</span>
    </div>
  )
}
