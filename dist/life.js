(function () {
  var canvas = document.getElementById("life");
  if (!canvas || canvas.dataset.ready === "1") return;
  canvas.dataset.ready = "1";

  var ctx = canvas.getContext("2d");
  if (!ctx) return;

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var cols = 0;
  var rows = 0;
  var grid = new Uint8Array(0);
  var pitchX = 7;
  var pitchY = 7;
  var still = 0;
  var lastHash = 0;
  var timer = 0;
  var running = false;
  var glider = [
    [0, 1, 0],
    [0, 0, 1],
    [1, 1, 1],
  ];

  function at(x, y) {
    return y * cols + x;
  }

  function stamp(pattern, ox, oy) {
    for (var y = 0; y < pattern.length; y++) {
      for (var x = 0; x < pattern[y].length; x++) {
        if (!pattern[y][x]) continue;
        grid[at((ox + x + cols) % cols, (oy + y + rows) % rows)] = 1;
      }
    }
  }

  function seed() {
    grid = new Uint8Array(cols * rows);
    for (var i = 0; i < grid.length; i++) grid[i] = Math.random() < 0.18 ? 1 : 0;
    var ships = 2 + ((Math.random() * 3) | 0);
    for (var n = 0; n < ships; n++) {
      stamp(glider, (Math.random() * cols) | 0, (Math.random() * rows) | 0);
    }
    still = 0;
    lastHash = 0;
  }

  function hash() {
    var h = 2213882213;
    for (var i = 0; i < grid.length; i++) {
      h ^= grid[i];
      h = Math.imul(h, 16777619);
    }
    return h;
  }

  function step() {
    var next = new Uint8Array(grid.length);
    var pop = 0;
    for (var y = 0; y < rows; y++) {
      for (var x = 0; x < cols; x++) {
        var neighbors = 0;
        for (var dy = -1; dy <= 1; dy++) {
          for (var dx = -1; dx <= 1; dx++) {
            if (dx === 0 && dy === 0) continue;
            neighbors += grid[at((x + dx + cols) % cols, (y + dy + rows) % rows)];
          }
        }
        var alive = grid[at(x, y)];
        var live = neighbors === 3 || (alive && neighbors === 2) ? 1 : 0;
        next[at(x, y)] = live;
        pop += live;
      }
    }
    grid = next;
    if (pop === 0) {
      seed();
      return;
    }
    var current = hash();
    if (current === lastHash) still += 1;
    else {
      still = 0;
      lastHash = current;
    }
    if (still > 12) {
      stamp(glider, (Math.random() * cols) | 0, (Math.random() * rows) | 0);
      still = 0;
    }
  }

  function draw() {
    var width = canvas.clientWidth;
    var height = canvas.clientHeight;
    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.globalAlpha = 0.82;
    for (var y = 0; y < rows; y++) {
      for (var x = 0; x < cols; x++) {
        if (!grid[at(x, y)]) continue;
        ctx.fillStyle = "hsl(" + Math.round((x / cols) * 360) + " 62% 82%)";
        ctx.fillRect(
          x * pitchX,
          y * pitchY,
          Math.max(1, pitchX - 1),
          Math.max(1, pitchY - 1)
        );
      }
    }
    ctx.restore();
  }

  function fit() {
    var width = canvas.clientWidth;
    var height = canvas.clientHeight;
    if (width < 1 || height < 1) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var bitmapW = Math.max(1, Math.round(width * dpr));
    var bitmapH = Math.max(1, Math.round(height * dpr));
    if (canvas.width !== bitmapW || canvas.height !== bitmapH) {
      canvas.width = bitmapW;
      canvas.height = bitmapH;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var nextCols = Math.max(16, Math.round(width / 7));
    var nextRows = Math.max(4, Math.round(height / 7));
    pitchX = width / nextCols;
    pitchY = height / nextRows;
    if (nextCols !== cols || nextRows !== rows) {
      cols = nextCols;
      rows = nextRows;
      seed();
    }
    draw();
  }

  fit();
  if (reduce) return;

  function start() {
    if (running) return;
    running = true;
    timer = window.setInterval(function () {
      step();
      draw();
    }, 170);
  }

  function stop() {
    window.clearInterval(timer);
    running = false;
  }

  start();
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) stop();
    else start();
  });

  if (typeof ResizeObserver === "function") new ResizeObserver(fit).observe(canvas);
  else window.addEventListener("resize", fit);
})();
