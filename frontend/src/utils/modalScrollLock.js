// Shared across dialogs so closing one window cannot unlock another.
let locks = 0
let previousOverflow = ''
let previousPadding = ''

export function lockModalScroll() {
  if (locks++ === 0) {
    previousOverflow = document.documentElement.style.overflow
    previousPadding = document.body.style.paddingRight
    const scrollbar = window.innerWidth - document.documentElement.clientWidth
    if (scrollbar > 0) {
      document.body.style.paddingRight = `${parseFloat(getComputedStyle(document.body).paddingRight) + scrollbar}px`
    }
    document.documentElement.style.overflow = 'hidden'
  }
  let released = false
  return () => {
    if (released) return
    released = true
    if (--locks === 0) {
      document.documentElement.style.overflow = previousOverflow
      document.body.style.paddingRight = previousPadding
    }
  }
}
