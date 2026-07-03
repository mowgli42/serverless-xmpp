<script>
  import { hashCells } from './display.js';

  /** @type {{ contentHash?: string, hashBlocks?: string[], grid?: number, showHex?: boolean }} */
  let {
    contentHash = '',
    hashBlocks = [],
    grid = 8,
    showHex = true,
  } = $props();

  let hex = $derived(
    contentHash.startsWith('SHA256:') ? contentHash.slice(7) : contentHash
  );

  let cells = $derived(hashCells(contentHash, hashBlocks, grid));
</script>

<div class="hash-panel" aria-label="Address book content fingerprint">
  {#if showHex && hex}
    <p class="hash-hex" title={contentHash}>
      <span class="label">SHA256</span>
      <code>{hex.slice(0, 16)}…{hex.slice(-8)}</code>
    </p>
  {/if}
  <div
    class="hash-grid"
    style="--grid: {grid}"
    role="img"
    aria-label="Visual hash fingerprint"
  >
    {#each cells as color, i (i)}
      <span class="hash-cell" style="background-color: {color}"></span>
    {/each}
  </div>
</div>

<style>
  .hash-panel {
    margin: 0.5rem 0;
  }
  .hash-hex {
    font-size: 0.7rem;
    color: #94a3b8;
    margin: 0 0 0.35rem 0;
    word-break: break-all;
  }
  .hash-hex .label {
    color: #64748b;
    margin-right: 0.35rem;
  }
  .hash-grid {
    display: grid;
    grid-template-columns: repeat(var(--grid), 1fr);
    gap: 2px;
    width: min(100%, 160px);
    aspect-ratio: 1;
  }
  .hash-cell {
    border-radius: 2px;
    min-height: 0;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
  }
</style>
