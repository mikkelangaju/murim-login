// Fill the reader's canvas. If Books scales a wide canvas down to the phone,
// compensate the authored sizes so the resulting text stays readable.
// Leave the viewport and visualViewport alone so pinch zoom is preserved.
(() => {
  const root = document.documentElement;
  let lastScale = 0;

  function fitWidth() {
    const screenWidth = window.screen.width || window.innerWidth;
    const scale = Math.max(1, window.innerWidth / screenWidth);
    if (!Number.isFinite(scale) || scale === lastScale) return;
    lastScale = scale;
    root.style.setProperty("--popup-scale", String(scale));
  }

  fitWidth();
  window.addEventListener("resize", fitWidth);
  window.addEventListener("orientationchange", fitWidth);
})();
