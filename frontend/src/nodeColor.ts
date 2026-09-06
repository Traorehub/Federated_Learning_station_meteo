/** Témoin en tungstène, nœud dégradé en braise : même code dans toutes les vues. */
const NODE_COLOR: Record<number, string> = { 1: '#e8b45a', 2: '#c45c3e' }

export function nodeColor(nodeId: number): string {
  return NODE_COLOR[nodeId] ?? '#a89880'
}
