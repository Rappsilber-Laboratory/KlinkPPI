import { computeStatistics } from './analysis'
self.onmessage = ({ data }) => {
    try { self.postMessage({ stats: computeStatistics(data.graph, data.databases) }) }
    catch (error) { self.postMessage({ error: error.message }) }
}
