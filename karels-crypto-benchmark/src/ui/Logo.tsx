export function Logo() {
  return (
    <div className="logo-cells" aria-hidden="true">
      {[...'KAREL'].map((c, i) => (
        <span key={i}>{c}</span>
      ))}
    </div>
  )
}
