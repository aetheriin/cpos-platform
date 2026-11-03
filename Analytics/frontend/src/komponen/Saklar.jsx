// Saklar nyala/mati yang bisa dipakai dengan keyboard dan dibaca pembaca layar (role="switch"). label menjelaskan fungsinya, mis. "Akses PR & PO Outstanding".
export default function Saklar({ nyala, onUbah, label, nonaktif = false }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={nyala}
      aria-label={label}
      disabled={nonaktif}
      onClick={() => onUbah(!nyala)}
      className={
        'inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 ' +
        (nyala ? 'bg-sky-600' : 'bg-slate-300')
      }
    >
      <span className={'ml-0.5 inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ' + (nyala ? 'translate-x-4' : 'translate-x-0')} />
    </button>
  )
}
