(function () {
  var el = document.querySelector(".phrase");
  var data = document.getElementById("phrases");
  if (!el || !data || el.dataset.ready === "1") return;

  var lines;
  try {
    lines = JSON.parse(data.textContent || "");
  } catch (err) {
    return;
  }
  if (!Array.isArray(lines) || lines.length < 2) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  el.dataset.ready = "1";
  var index = 0;
  window.setInterval(function () {
    el.classList.add("is-fading");
    window.setTimeout(function () {
      index = (index + 1) % lines.length;
      el.textContent = lines[index];
      el.classList.remove("is-fading");
    }, 550);
  }, 4600);
})();
