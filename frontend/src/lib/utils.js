import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const cn = (...a) => twMerge(clsx(a))

export const fmtDate = (d) =>
  new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })

export const fmtDateTime = (d) =>
  new Date(d).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

export const fmtBytes = (b) => {
  if (!b) return '—'
  const u = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(b) / Math.log(1024))
  return `${(b / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`
}

export const titleCase = (s = '') =>
  s.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
