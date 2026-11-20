<template>
  <Teleport to="body">
    <dialog ref="dialog" class="world-dialog" :aria-labelledby="titleId" @cancel.prevent="dismiss" @close="closed" @keydown.tab="trapTab" @pointerdown="backdropStart" @pointerup="backdropEnd">
      <div class="dialog-surface">
        <header class="dialog-header">
          <div><h2 :id="titleId">{{ title }}</h2><p v-if="subtitle">{{ subtitle }}</p></div>
          <button type="button" class="dialog-close" :aria-label="`关闭${title}`" autofocus @click="dismiss">×</button>
        </header>
        <div class="dialog-content"><slot /></div>
      </div>
    </dialog>
  </Teleport>
</template>

<script setup>
import {ref, watch, onMounted, onBeforeUnmount, useId} from 'vue'
import {lockModalScroll} from '../utils/modalScrollLock'

const props = defineProps({modelValue: Boolean, title: String, subtitle: String})
const emit = defineEmits(['update:modelValue'])
const dialog = ref(null), titleId = useId()
let unlock = null, returnFocus = null, backdropPressed = false
const dismiss = () => emit('update:modelValue', false)
function release() {
  unlock?.()
  unlock = null
  if (returnFocus?.isConnected) returnFocus.focus({preventScroll: true})
  returnFocus = null
}
function closed() {
  // Ignore a queued close event if the same window has already reopened.
  if (dialog.value?.open) return
  release()
  if (props.modelValue) dismiss()
}
function trapTab(event) {
  const items = [...dialog.value.querySelectorAll('button, a[href], input, select, textarea, summary, [tabindex]')]
    .filter(node => !node.disabled && node.tabIndex >= 0 && node.checkVisibility())
  if (!items.length) { event.preventDefault(); return }
  const first = items[0], last = items[items.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.value)) {
    event.preventDefault()
    first.focus()
  }
}
function sync() {
  const node = dialog.value
  if (!node) return
  if (props.modelValue && !node.open) {
    returnFocus = document.activeElement
    unlock = lockModalScroll()
    node.showModal()
  } else if (!props.modelValue && node.open) {
    node.close()
    release()
  }
}
function outside(event) {
  if (event.target !== dialog.value) return false
  const rect = dialog.value.getBoundingClientRect()
  return event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom
}
function backdropStart(event) { backdropPressed = outside(event) }
function backdropEnd(event) {
  if (backdropPressed && outside(event)) dismiss()
  backdropPressed = false
}
watch(() => props.modelValue, sync, {flush: 'post'})
onMounted(sync)
onBeforeUnmount(() => { dialog.value?.close(); release() })
</script>

<style scoped>
.world-dialog{width:min(960px,calc(100vw - 40px));max-width:none;max-height:calc(100dvh - 48px);margin:auto;padding:0;border:1px solid #d1ddd6;border-radius:12px;background:#fff;color:#202b24;box-shadow:0 24px 80px #172e2938;overflow:hidden}
.world-dialog::backdrop{background:rgba(26,40,35,.4)}
.dialog-surface{display:flex;flex-direction:column;max-height:calc(100dvh - 50px);min-height:0}
.dialog-header{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:20px 24px;border-bottom:1px solid #e3eae5;flex-shrink:0;background:#fff}
.dialog-header h2{font-size:18px;font-weight:600;margin:0;line-height:1.5}.dialog-header p{font-size:12px;color:#627168;margin:4px 0 0;line-height:1.6;overflow-wrap:anywhere}
.dialog-close{flex-shrink:0;display:grid;place-items:center;width:32px;height:32px;border:1px solid #d7e1da;border-radius:6px;background:#f6f9f7;color:#2e4436;font-size:22px;line-height:1;cursor:pointer}.dialog-close:hover{background:#e8f1eb}.dialog-close:focus-visible{outline:2px solid #147d68;outline-offset:3px}
.dialog-content{padding:20px 24px;overflow:auto;overscroll-behavior:contain;min-height:0;overflow-wrap:anywhere}
@media(max-width:600px){.world-dialog{width:calc(100vw - 20px);max-height:calc(100dvh - 24px);border-radius:9px}.dialog-surface{max-height:calc(100dvh - 26px)}.dialog-header{padding:14px 16px}.dialog-header h2{font-size:16px}.dialog-content{padding:16px}}
</style>
