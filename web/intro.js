// A pre-rendered rope film with a model-extracted alpha channel.
export function startIntro() {
  const overlay = document.createElement("div");
  overlay.className = "arrival rope-arrival film-arrival";
  overlay.setAttribute("role", "button");
  overlay.setAttribute("aria-label", "Enter Project 5.14");
  overlay.tabIndex = 0;
  overlay.innerHTML =
    '<div class="arrival-copy"><span class="arrival-wordmark">PROJECT <b>5.14</b></span></div><div class="rope-film-stage"><img class="rope-film-poster" src="/rope-poster.webp" alt="A neatly tied yellow climbing rope with blue tracer yarns"><video class="rope-film" muted playsinline loop preload="auto" aria-hidden="true"><source src="/rope-intro.webm" type="video/webm"></video></div><span class="enter-prompt">click anywhere to enter</span>';
  document.body.append(overlay);
  document.querySelector("#boot-cover")?.remove();
  const video = overlay.querySelector("video");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let disposed = false,
    requested = false,
    contentReady = false,
    exiting = false;
  let frame, fadeTimer, finishExit;
  const exited = new Promise((resolve) => {
    finishExit = resolve;
  });
  video.playbackRate = 0.8;
  video.addEventListener(
    "playing",
    () => overlay.classList.add("film-playing"),
    { once: true },
  );
  if (!reduced) video.play().catch(() => {});

  function fadeOut() {
    if (!contentReady || exiting || disposed) return;
    exiting = true;
    overlay.classList.add("arrival-exit");
    fadeTimer = setTimeout(finishExit, reduced ? 150 : 650);
  }
  function enter() {
    if (requested || disposed) return;
    requested = true;
    overlay.classList.add("entry-requested");
    if (!contentReady)
      overlay.querySelector(".enter-prompt").textContent = "Opening your plan…";
    if (!reduced) {
      const begin = performance.now();
      const accelerate = (now) => {
        if (disposed) return;
        const progress = Math.min(1, (now - begin) / 450);
        video.playbackRate = 0.8 + 7.2 * progress * progress;
        if (progress < 1) frame = requestAnimationFrame(accelerate);
      };
      frame = requestAnimationFrame(accelerate);
    }
    fadeOut();
  }
  overlay.addEventListener("click", enter);
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      enter();
    }
  });
  const close = () => {
    if (disposed) return;
    disposed = true;
    finishExit();
    clearTimeout(fadeTimer);
    cancelAnimationFrame(frame);
    video.pause();
    video.removeAttribute("src");
    video.querySelector("source")?.remove();
    video.load();
    overlay.remove();
  };
  return {
    close,
    async finish() {
      contentReady = true;
      if (requested) fadeOut();
      else overlay.focus({ preventScroll: true });
      await exited;
    },
  };
}
