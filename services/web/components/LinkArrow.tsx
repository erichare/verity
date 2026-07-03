type LinkArrowProps = {
  kind?: "right" | "external";
  className?: string;
};

export function LinkArrow({ kind = "right", className = "" }: LinkArrowProps) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`inline-block h-[0.85em] w-[0.85em] shrink-0 align-[-0.07em] ${className}`}
    >
      {kind === "external" ? (
        <>
          <path d="M5 4.75h6.25V11" />
          <path d="m4.75 11.25 6.25-6.5" />
        </>
      ) : (
        <>
          <path d="M3.75 8h8.5" />
          <path d="m8.75 4.5 3.5 3.5-3.5 3.5" />
        </>
      )}
    </svg>
  );
}
