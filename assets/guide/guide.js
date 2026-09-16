(function () {
  "use strict";

  /* ---------- preflight progress ---------- */
  var checks = Array.prototype.slice.call(document.querySelectorAll("[data-progress]"));
  var progressLabel = document.querySelector("[data-progress-label]");
  var progressBar = document.querySelector("[data-progress-bar]");

  function updateProgress() {
    var done = checks.filter(function (box) { return box.checked; }).length;
    if (progressLabel) progressLabel.textContent = done + "/" + checks.length;
    if (progressBar) progressBar.style.setProperty("--progress", (done / checks.length) * 100 + "%");
  }

  checks.forEach(function (box) { box.addEventListener("change", updateProgress); });
  updateProgress();

  /* ---------- print ---------- */
  var printButton = document.querySelector("[data-print]");
  if (printButton) printButton.addEventListener("click", function () { window.print(); });

  /* ---------- copy-able commands ---------- */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    var holder = document.createElement("textarea");
    holder.value = text;
    holder.setAttribute("readonly", "");
    holder.style.position = "fixed";
    holder.style.opacity = "0";
    document.body.appendChild(holder);
    holder.select();
    var ok = document.execCommand("copy");
    document.body.removeChild(holder);
    return ok ? Promise.resolve() : Promise.reject(new Error("copy failed"));
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-copy]"), function (button) {
    var original = button.textContent;
    button.addEventListener("click", function () {
      copyText(button.getAttribute("data-copy")).then(function () {
        button.textContent = "Đã chép";
        button.setAttribute("data-copied", "");
      }, function () {
        button.textContent = "Chép thủ công";
      });
      window.setTimeout(function () {
        button.textContent = original;
        button.removeAttribute("data-copied");
      }, 2000);
    });
  });

  /* ---------- screenshot lightbox ---------- */
  var lightbox = document.querySelector("[data-lightbox]");
  var triggers = Array.prototype.slice.call(document.querySelectorAll("[data-zoom]"));
  if (!lightbox || !triggers.length) return;

  var stage = lightbox.querySelector(".lightbox-stage");
  var stageImage = lightbox.querySelector("[data-lightbox-image]");
  var heading = lightbox.querySelector("[data-lightbox-heading]");
  var note = lightbox.querySelector("[data-lightbox-note]");
  var counter = lightbox.querySelector("[data-lightbox-count]");
  var prevButton = lightbox.querySelector("[data-lightbox-prev]");
  var nextButton = lightbox.querySelector("[data-lightbox-next]");
  var closeButton = lightbox.querySelector(".lightbox-close");
  var lastFocus = null;
  var current = -1;
  stageImage.addEventListener("load", function () { fitStageImage(); });

  function captionOf(trigger) {
    var figure = trigger.closest("figure");
    var caption = figure ? figure.querySelector("figcaption") : null;
    if (!caption) return "Ảnh hướng dẫn";
    // figcaption gồm nhãn loại ảnh và tên bước; nối bằng dấu chấm giữa để không dính chữ
    var parts = [];
    Array.prototype.forEach.call(caption.children.length ? caption.children : [caption], function (part) {
      var text = part.textContent.replace(/\s+/g, " ").trim();
      if (text) parts.push(text);
    });
    return parts.join(" · ");
  }

  // Chữ trong giao diện CVAT phải đọc được: ảnh cận cảnh phóng 2.5x, ảnh toàn màn hình
  // không bao giờ bị thu nhỏ dưới 900px — màn hẹp thì kéo ngang trong khung xem.
  function fitStageImage() {
    var natural = stageImage.naturalWidth;
    if (!natural) return;
    var stageWidth = stage.clientWidth || natural;
    var width = natural < 900 ? natural * 2.5 : Math.max(Math.min(natural, stageWidth), 900);
    stageImage.style.width = Math.round(width) + "px";
  }

  function show(index) {
    if (index < 0) index = triggers.length - 1;
    if (index >= triggers.length) index = 0;
    current = index;

    var trigger = triggers[current];
    var image = trigger.querySelector("img");
    stageImage.style.width = "auto";
    stageImage.src = image.getAttribute("src");
    if (stageImage.complete) fitStageImage();
    stageImage.alt = image.getAttribute("alt") || "";
    heading.textContent = captionOf(trigger);
    note.textContent = trigger.getAttribute("data-zoom-note") || image.getAttribute("alt") || "";
    counter.textContent = current + 1 + "/" + triggers.length;
    stage.scrollLeft = 0;
    stage.scrollTop = 0;
  }

  window.addEventListener("resize", function () {
    if (!lightbox.hidden) fitStageImage();
  });

  function open(index) {
    lastFocus = document.activeElement;
    show(index);
    lightbox.hidden = false;
    document.body.classList.add("lightbox-open");
    if (closeButton) closeButton.focus();
  }

  function close() {
    lightbox.hidden = true;
    document.body.classList.remove("lightbox-open");
    stageImage.removeAttribute("src");
    // không để focus kẹt lại trong hộp đã ẩn: trả về nút vừa bấm, nếu không có thì về ảnh đang xem
    var usable = lastFocus && lastFocus !== document.body && !lightbox.contains(lastFocus);
    var back = usable ? lastFocus : triggers[current];
    if (back && typeof back.focus === "function") back.focus();
  }

  triggers.forEach(function (trigger, index) {
    trigger.addEventListener("click", function (event) {
      event.preventDefault();
      open(index);
    });
  });

  Array.prototype.forEach.call(lightbox.querySelectorAll("[data-lightbox-close]"), function (button) {
    button.addEventListener("click", close);
  });
  if (prevButton) prevButton.addEventListener("click", function () { show(current - 1); });
  if (nextButton) nextButton.addEventListener("click", function () { show(current + 1); });

  document.addEventListener("keydown", function (event) {
    if (lightbox.hidden) return;
    if (event.key === "Escape") { event.preventDefault(); close(); }
    else if (event.key === "ArrowLeft") { event.preventDefault(); show(current - 1); }
    else if (event.key === "ArrowRight") { event.preventDefault(); show(current + 1); }
    else if (event.key === "Tab") {
      // keep focus inside the dialog
      var focusable = lightbox.querySelectorAll("button");
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
})();
