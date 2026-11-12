import { IkonPanah } from './Ikon'

// Dropdown pilihan tunggal. Panah bawaan browser dimatikan dan diganti IkonPanah yang sama di semua dropdown aplikasi,
// jadi tampilannya seragam di semua browser. className dipasang di pembungkus (untuk margin dan lebar); props lain ke <select>.
export default function Select({ otomatis = false, kecil = false, className = '', children, ...props }) {
  return (
    <div className={'relative ' + (otomatis ? 'inline-block ' : 'block ') + className}>
      <select
        {...props}
        className={
          'w-full appearance-none rounded-md border border-slate-300 bg-white text-sm text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:opacity-50 ' +
          (kecil ? 'py-1 pl-2 pr-7' : 'py-2 pl-3 pr-9')
        }
      >
        {children}
      </select>
      <IkonPanah className={'pointer-events-none absolute top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 ' + (kecil ? 'right-1.5' : 'right-3')} />
    </div>
  )
}
