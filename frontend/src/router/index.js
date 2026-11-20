import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import AudienceSimulation from '../views/AudienceSimulation.vue'
import ScreenPlanning from '../views/ScreenPlanning.vue'
import AudienceWorld from '../views/AudienceWorld.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'

const routes = [
  { path: '/world', name: 'AudienceWorld', component: AudienceWorld },
  { path: '/planning', name: 'ScreenPlanning', component: ScreenPlanning },
  { path: '/audience-demo', name: 'AudienceDemo', component: AudienceSimulation },
  { path: '/legacy', name: 'LegacyHome', component: Home },
  {
    path: '/',
    name: 'Home',
    component: AudienceWorld
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
