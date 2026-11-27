<template>
  <section class="locations" aria-label="库存地点与人群模拟">
    <h2>屏幕地点与场景准备</h2>
    <p v-if="inventory">{{ inventory.sheet }} · {{ inventory.total }} 块屏幕 · {{ inventory.valid_coordinates }} 个有效坐标。库存地址仅供参考，模拟时会查证周边地图。</p>
    <p v-else>{{ loading ? '正在提取每块屏幕的位置…' : '尚未读取地点' }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <details>
      <summary>全部屏幕地点<span v-if="inventory">{{ inventory.total }} 块屏幕</span></summary>
      <div class="location-content">
        <div class="tools">
          <input v-model="search" placeholder="搜索屏幕、地址、POI" aria-label="搜索屏幕地点">
          <button :disabled="loading" @click="load">重新提取</button>
        </div>
        <div class="location-table">
          <table>
            <thead><tr><th>屏幕 / 库存地址</th><th>经纬度（WGS84）</th><th>地点状态</th></tr></thead>
            <tbody>
              <tr v-for="f in filtered" :key="f.key">
                <td>{{ f.address || f.poi || '未提供地址' }}<small>{{ f.screen_id }}</small></td>
                <td>{{ f.coordinate ? `${f.coordinate.lat.toFixed(6)}, ${f.coordinate.lon.toFixed(6)}` : '缺失' }}<small>{{ f.coordinate?.source }}</small></td>
                <td>{{ f.error || '坐标已解析 · 地图待查证' }}</td>
              </tr>
              <tr v-if="!loading && !filtered.length"><td colspan="3">{{ search ? '没有匹配的屏幕地点' : '暂无屏幕地点' }}</td></tr>
            </tbody>
          </table>
        </div>
        <small>按 GEOM 定位；缺少 GEOM 时使用经纬度字段。</small>
      </div>
    </details>
  </section>
</template>
<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import api from '../api'
const props = defineProps({ projectId: String })
const inventory = ref(null), loading = ref(false), error = ref(''), search = ref('')
let ticket = 0
onBeforeUnmount(() => ticket++)
const filtered = computed(() => (inventory.value?.frames || []).filter(f => `${f.screen_id} ${f.address} ${f.poi}`.toLowerCase().includes(search.value.toLowerCase())))
async function load() {
  const v = ++ticket
  loading.value = true
  error.value = ''
  try {
    const r = await api.post('/api/world/geo-inventory', { project_id: props.projectId })
    if (v !== ticket) return
    inventory.value = r.data
  } catch (e) {
    if (v === ticket) error.value = e.message
  } finally {
    if (v === ticket) loading.value = false
  }
}
watch(() => props.projectId, () => { inventory.value = null; search.value = ''; load() }, { immediate: true })
</script>
<style scoped>.locations{background:white;border:1px solid #dbe2d7;border-radius:12px;padding:22px;margin-bottom:20px;color:#233a2c}h2{font-size:18px}p{font-size:12px;line-height:1.8;color:#627267}.tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap}input{flex:1;min-width:160px}input,button{padding:9px;border:1px solid #c7d8cc;border-radius:5px;background:white;color:#285a40;font:inherit;font-size:12px}button{cursor:pointer}button:disabled{opacity:.5}.location-table{overflow:auto;max-height:370px;margin:14px 0}table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;border-bottom:1px solid #e2e9e4;padding:10px;min-width:65px}td:first-child{min-width:220px}th{background:#f4f8f5;position:sticky;top:0}small{display:block;font-size:10px;color:#6b7b70;line-height:1.8;margin-top:5px}summary{display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer;font-weight:600;padding:12px 0}summary::after{content:"展开 ▾";font-size:12px;color:#285a40}details[open]>summary::after{content:"收起 ▴"}.location-content{padding-top:8px}</style>
