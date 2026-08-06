// Bridge between an embedded demo and the docs page hosting it.
//
// Posts the document height whenever it changes so the host can size the
// iframe, and accepts a theme message so the demo follows the docs theme
// toggle. Both directions are same-origin: the host is the docs site itself.

(function () {
  var hostOrigin = location.origin;
  // Measure the content, not the root element's box. The host sizes this
  // iframe from what we report, and documentElement's box is clamped to that
  // viewport, so measuring it feeds our own answer back and latches at the
  // smallest value we ever sent. body.scrollHeight is content-driven.
  function contentHeight() {
    var body = document.body;
    if (!body) return 0;
    var style = window.getComputedStyle(body);
    var margins = parseFloat(style.marginTop) + parseFloat(style.marginBottom);
    return Math.ceil(body.scrollHeight + (isNaN(margins) ? 0 : margins));
  }

  var last = -1;
  function postHeight() {
    var height = contentHeight();
    // Round to a step so a sub-pixel reflow cannot start a resize ping-pong.
    if (Math.abs(height - last) < 4) return;
    last = height;
    parent.postMessage({ type: "celeris-demo-height", height: height }, hostOrigin);
  }

  if (typeof ResizeObserver === "function") {
    // Observe body: it grows with content. Observing documentElement would only
    // ever report the viewport we were just given.
    new ResizeObserver(postHeight).observe(document.body);
  }
  // Content that arrives after first paint (a mounting framework app, a reply
  // landing) changes body's height without resizing it in a way every browser
  // reports, so watch the tree too.
  new MutationObserver(postHeight).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  window.addEventListener("load", postHeight);

  window.addEventListener("message", function (event) {
    if (event.source !== parent || event.origin !== hostOrigin) return;
    var data = event.data;
    if (!data || data.type !== "celeris-demo-theme") return;
    if (data.theme === "dark" || data.theme === "light") {
      document.documentElement.dataset.theme = data.theme;
    }
  });

  // The host may set the initial theme in the URL so the first paint matches.
  var initial = new URLSearchParams(location.search).get("theme");
  if (initial === "dark" || initial === "light") {
    document.documentElement.dataset.theme = initial;
  }
})();
